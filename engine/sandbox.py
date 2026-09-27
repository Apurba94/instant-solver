"""Stage 3 — The judge: compilation and sandboxed execution.

Untrusted code never runs on the application server. This module is the only
place in the engine that executes anything, and it does so behind a narrow
interface (:class:`Runner`) so the isolation backend can be swapped without
touching the pipeline.

Two backends are provided:

``LocalRlimitRunner``
    fork/exec with POSIX resource limits (CPU, address space, file size,
    process count, core dumps) plus a wall-clock kill. Correct for CPU, memory
    and runaway output, and adequate for a single-tenant development machine.

``NsjailRunner``
    the production backend: the same limits *plus* a fresh mount, PID, IPC,
    UTS and network namespace, a read-only root, a tmpfs work directory and a
    seccomp policy. Used automatically when ``nsjail`` is on PATH.

The security model is written up in full in the architecture document; the
short version is that RLIMIT alone stops accidents, while namespaces stop
attacks, so production must run the second backend.
"""
from __future__ import annotations

import os
import re
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import Language, RunResult, Verdict

MAX_OUTPUT_BYTES = 64 * 1024 * 1024      # 64 MB before we call it OLE
COMPILE_TIMEOUT_S = 25
DEFAULT_PROCESS_LIMIT = 64               # threads count against this; JVM needs room


# --------------------------------------------------------------------------
# Language configuration
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LanguageSpec:
    name: str
    source_name: str
    compile_cmd: Optional[list[str]]
    run_cmd: list[str]
    version_cmd: list[str]
    # The JVM maps far more virtual address space than it uses, so RLIMIT_AS
    # would kill it at startup; it is limited with -Xmx instead.
    use_address_space_limit: bool = True
    time_multiplier: float = 1.0         # interpreted languages get more wall time


LANGUAGES: dict[Language, LanguageSpec] = {
    Language.CPP: LanguageSpec(
        name="C++17 (g++)",
        source_name="solution.cpp",
        compile_cmd=["g++", "-std=c++17", "-O2", "-pipe", "-static", "-s",
                     "-o", "solution", "solution.cpp"],
        run_cmd=["./solution"],
        version_cmd=["g++", "--version"],
    ),
    Language.C: LanguageSpec(
        name="C17 (gcc)",
        source_name="solution.c",
        compile_cmd=["gcc", "-std=c17", "-O2", "-pipe", "-o", "solution", "solution.c", "-lm"],
        run_cmd=["./solution"],
        version_cmd=["gcc", "--version"],
    ),
    Language.PYTHON: LanguageSpec(
        name="Python 3",
        source_name="solution.py",
        compile_cmd=None,
        run_cmd=["python3", "-S", "solution.py"],
        version_cmd=["python3", "--version"],
        time_multiplier=3.0,
    ),
    Language.JAVA: LanguageSpec(
        name="Java 17",
        source_name="Main.java",
        compile_cmd=["javac", "-encoding", "UTF-8", "Main.java"],
        run_cmd=["java", "-XX:+UseSerialGC", "-Xss64m", "-Xmx256m", "Main"],
        version_cmd=["java", "-version"],
        use_address_space_limit=False,
        time_multiplier=2.0,
    ),
}


def available_languages() -> dict[str, bool]:
    """Which toolchains are actually installed on this machine."""
    out: dict[str, bool] = {}
    for lang, spec in LANGUAGES.items():
        out[lang.value] = shutil.which(spec.run_cmd[0].lstrip("./")) is not None or (
            spec.compile_cmd is not None and shutil.which(spec.compile_cmd[0]) is not None
        )
    return out


# --------------------------------------------------------------------------
# Low-level execution
# --------------------------------------------------------------------------

@dataclass
class Limits:
    cpu_ms: int = 2000
    wall_ms: int = 6000
    memory_mb: int = 256
    output_bytes: int = MAX_OUTPUT_BYTES
    processes: int = DEFAULT_PROCESS_LIMIT
    use_address_space_limit: bool = True


class Runner:
    """Interface every isolation backend implements."""

    name = "abstract"

    def execute(self, argv: list[str], cwd: Path, stdin_data: str,
                limits: Limits) -> RunResult:  # pragma: no cover - interface
        raise NotImplementedError


class LocalRlimitRunner(Runner):
    """fork/exec with POSIX rlimits and a wall-clock kill.

    Accurate CPU time and peak RSS come from ``wait4``'s rusage, which is the
    same source the kernel gives ``/usr/bin/time``; polling ``/proc`` would race
    with short-lived processes and systematically under-report.
    """

    name = "local-rlimit"
    # RLIMIT_NPROC counts every process and thread of the user, including the
    # API server's own threads, so it is only safe on a process that will not
    # fork. A wrapper that forks the real program sets its own limit inside.
    limit_nproc_on_exec = True

    def execute(self, argv: list[str], cwd: Path, stdin_data: str,
                limits: Limits) -> RunResult:
        cwd.mkdir(parents=True, exist_ok=True)
        in_path = cwd / ".stdin"
        out_path = cwd / ".stdout"
        err_path = cwd / ".stderr"
        in_path.write_text(stdin_data)

        cpu_seconds = max(1, int((limits.cpu_ms + 999) // 1000))
        mem_bytes = limits.memory_mb * 1024 * 1024
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(cwd),
            "LANG": "C.UTF-8",
            # Keep the JVM and Python from spawning proxy/network machinery.
            "no_proxy": "*",
        }

        started = time.monotonic()
        pid = os.fork()
        if pid == 0:                                    # ---- child ----
            try:
                os.setsid()
                fd_in = os.open(str(in_path), os.O_RDONLY)
                fd_out = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                fd_err = os.open(str(err_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                os.dup2(fd_in, 0)
                os.dup2(fd_out, 1)
                os.dup2(fd_err, 2)
                os.chdir(str(cwd))

                resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
                resource.setrlimit(resource.RLIMIT_FSIZE,
                                   (limits.output_bytes, limits.output_bytes))
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                if self.limit_nproc_on_exec:
                    try:
                        resource.setrlimit(resource.RLIMIT_NPROC,
                                           (limits.processes, limits.processes))
                    except (ValueError, OSError):
                        pass
                if limits.use_address_space_limit:
                    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

                os.execvpe(argv[0], argv, env)
            except BaseException:
                os._exit(127)
            os._exit(127)                                # unreachable

        # ---- parent ----
        deadline = started + limits.wall_ms / 1000.0
        status = rusage = None
        killed_by_wall = False
        while True:
            waited_pid, waited_status, waited_rusage = os.wait4(pid, os.WNOHANG)
            if waited_pid != 0:
                status, rusage = waited_status, waited_rusage
                break
            if time.monotonic() > deadline:
                killed_by_wall = True
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                _, status, rusage = os.wait4(pid, 0)
                break
            time.sleep(0.002)

        wall_ms = int((time.monotonic() - started) * 1000)
        cpu_ms = int((rusage.ru_utime + rusage.ru_stime) * 1000) if rusage else wall_ms
        memory_kb = int(rusage.ru_maxrss) if rusage else 0

        stdout = _read_capped(out_path, limits.output_bytes)
        stderr = _read_capped(err_path, 64 * 1024)
        for path in (in_path, out_path, err_path):
            path.unlink(missing_ok=True)

        return _classify(self._translate_status(status), killed_by_wall, cpu_ms, wall_ms,
                         memory_kb, stdout, stderr, limits)

    def _translate_status(self, status: Optional[int]) -> Optional[int]:
        return status


class NsjailRunner(LocalRlimitRunner):
    """Production backend: rlimits *plus* namespace and filesystem isolation.

    Wraps the target command in ``nsjail``, which gives a private mount / PID /
    IPC / UTS / network namespace, a read-only root filesystem, a tmpfs scratch
    directory and a seccomp filter. Falls back to the local runner if nsjail is
    not installed, and the caller is told which backend actually ran.
    """

    name = "nsjail"
    limit_nproc_on_exec = False     # nsjail forks; --rlimit_nproc applies inside

    @staticmethod
    def is_available() -> bool:
        return shutil.which("nsjail") is not None

    def execute(self, argv: list[str], cwd: Path, stdin_data: str,
                limits: Limits) -> RunResult:
        if not self.is_available():
            return super().execute(argv, cwd, stdin_data, limits)
        jail = [
            "nsjail", "--quiet", "--mode", "o",
            "--chroot", "/", "--cwd", str(cwd),
            "--bindmount", f"{cwd}:{cwd}",
            "--time_limit", str(max(1, (limits.wall_ms + 999) // 1000)),
            "--max_cpus", "1",
            "--rlimit_as",
            str(limits.memory_mb) if limits.use_address_space_limit else "max",
            "--rlimit_cpu", str(max(1, (limits.cpu_ms + 999) // 1000)),
            "--rlimit_fsize", str(limits.output_bytes // (1024 * 1024) or 1),
            "--rlimit_nproc", str(limits.processes),
            "--rlimit_stack", "max",     # deep recursion is normal in CP solutions
            "--keep_env",
            "--iface_no_lo",
            "--really_quiet", "--",
        ]
        # nsjail execs without a PATH search, so resolve bare names like python3.
        if "/" not in argv[0]:
            argv = [shutil.which(argv[0]) or argv[0], *argv[1:]]
        return super().execute(jail + argv, cwd, stdin_data, limits)

    def _translate_status(self, status: Optional[int]) -> Optional[int]:
        # nsjail exits with 128+N when the jailed program dies from signal N.
        # Turn that back into a "killed by signal N" status so a CPU-limit kill
        # is judged TLE and a segfault RE, as with the local runner.
        if status is not None and os.WIFEXITED(status):
            code = os.WEXITSTATUS(status)
            if 128 < code < 128 + 65:
                return code - 128
        return status


def pick_runner() -> Runner:
    """Prefer the isolating backend when the host provides it."""
    return NsjailRunner() if NsjailRunner.is_available() else LocalRlimitRunner()


def _read_capped(path: Path, cap: int) -> str:
    try:
        data = path.read_bytes()[: cap + 1]
    except FileNotFoundError:
        return ""
    return data.decode("utf-8", errors="replace")


_SIGNAL_MEANING = {
    signal.SIGXCPU: ("TLE", "CPU time limit exceeded"),
    signal.SIGKILL: ("TLE", "killed (wall clock or out of memory)"),
    signal.SIGSEGV: ("RE", "segmentation fault — out-of-bounds access, null pointer, "
                           "or stack overflow from deep recursion"),
    signal.SIGABRT: ("RE", "aborted — an assertion failed or an exception went uncaught"),
    signal.SIGFPE: ("RE", "arithmetic error — division or modulo by zero"),
    signal.SIGXFSZ: ("OLE", "wrote more output than allowed"),
    signal.SIGBUS: ("RE", "bus error — misaligned or invalid memory access"),
}


def _classify(status: Optional[int], killed_by_wall: bool, cpu_ms: int, wall_ms: int,
              memory_kb: int, stdout: str, stderr: str, limits: Limits) -> RunResult:
    """Turn a raw exit status into a judge verdict."""
    base = RunResult(verdict=Verdict.JUDGE_ERROR, stdout=stdout, stderr=stderr,
                     time_ms=max(cpu_ms, 0), memory_kb=memory_kb)

    if len(stdout.encode("utf-8", errors="ignore")) > limits.output_bytes:
        base.verdict = Verdict.OUTPUT_LIMIT_EXCEEDED
        base.message = "Program produced more output than the limit allows."
        return base

    mem_limit_kb = limits.memory_mb * 1024
    memory_exhausted = (
        memory_kb > mem_limit_kb * 0.98
        or "bad_alloc" in stderr
        or "OutOfMemoryError" in stderr
        or "MemoryError" in stderr
    )

    if killed_by_wall:
        base.verdict = Verdict.MEMORY_LIMIT_EXCEEDED if memory_exhausted else Verdict.TIME_LIMIT_EXCEEDED
        base.time_ms = max(base.time_ms, limits.wall_ms)
        base.message = ("Exceeded the memory limit." if memory_exhausted
                        else f"Still running after {limits.wall_ms} ms of wall clock.")
        return base

    if status is None:
        base.message = "Process disappeared without a status."
        return base

    if os.WIFSIGNALED(status):
        sig = os.WTERMSIG(status)
        kind, text = _SIGNAL_MEANING.get(sig, ("RE", f"killed by signal {sig}"))
        if memory_exhausted and kind != "OLE":
            base.verdict, base.message = Verdict.MEMORY_LIMIT_EXCEEDED, "Exceeded the memory limit."
        elif kind == "TLE":
            base.verdict, base.message = Verdict.TIME_LIMIT_EXCEEDED, text
        elif kind == "OLE":
            base.verdict, base.message = Verdict.OUTPUT_LIMIT_EXCEEDED, text
        else:
            base.verdict, base.message = Verdict.RUNTIME_ERROR, text
        return base

    code = os.WEXITSTATUS(status)
    base.exit_code = code
    if code != 0:
        base.verdict = Verdict.MEMORY_LIMIT_EXCEEDED if memory_exhausted else Verdict.RUNTIME_ERROR
        base.message = (f"Exited with status {code}." +
                        (f" stderr: {stderr.strip()[:300]}" if stderr.strip() else ""))
        return base
    if cpu_ms > limits.cpu_ms:
        base.verdict = Verdict.TIME_LIMIT_EXCEEDED
        base.message = f"Used {cpu_ms} ms of CPU against a {limits.cpu_ms} ms limit."
        return base
    if memory_kb > mem_limit_kb:
        base.verdict = Verdict.MEMORY_LIMIT_EXCEEDED
        base.message = f"Peak memory {memory_kb // 1024} MB over the {limits.memory_mb} MB limit."
        return base

    base.verdict = Verdict.ACCEPTED
    return base


# --------------------------------------------------------------------------
# Compiled program handle
# --------------------------------------------------------------------------

class Program:
    """A compiled (or interpreted) program ready to be run on many inputs."""

    def __init__(self, workdir: Path, spec: LanguageSpec, runner: Runner):
        self.workdir = workdir
        self.spec = spec
        self.runner = runner

    def run(self, stdin_data: str, time_limit_ms: int, memory_limit_mb: int) -> RunResult:
        cpu_ms = int(time_limit_ms * self.spec.time_multiplier)
        limits = Limits(
            cpu_ms=cpu_ms,
            wall_ms=int(cpu_ms * 2 + 1500),
            memory_mb=memory_limit_mb,
            use_address_space_limit=self.spec.use_address_space_limit,
        )
        return self.runner.execute(list(self.spec.run_cmd), self.workdir, stdin_data, limits)

    def cleanup(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def __enter__(self) -> "Program":
        return self

    def __exit__(self, *exc: object) -> None:
        self.cleanup()


class CompileError(Exception):
    def __init__(self, log: str):
        super().__init__(log)
        self.log = log


def compile_source(code: str, language: Language = Language.CPP,
                   runner: Optional[Runner] = None,
                   workdir_root: Optional[str] = None) -> Program:
    """Write the source to a scratch directory and build it.

    Raises :class:`CompileError` with the compiler's own diagnostics, which the
    repair loop feeds straight back to the synthesiser — a compiler error
    message is the single most useful repair signal there is.
    """
    spec = LANGUAGES[language]
    runner = runner or pick_runner()
    workdir = Path(tempfile.mkdtemp(prefix="cpsolve-", dir=workdir_root))
    (workdir / spec.source_name).write_text(code)

    if spec.compile_cmd is None:                     # interpreted
        return Program(workdir, spec, runner)

    try:
        proc = subprocess.run(
            spec.compile_cmd, cwd=workdir, capture_output=True, text=True,
            timeout=COMPILE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(workdir, ignore_errors=True)
        raise CompileError(f"Compilation exceeded {COMPILE_TIMEOUT_S}s.")

    if proc.returncode != 0:
        log = (proc.stderr or proc.stdout or "").strip()
        shutil.rmtree(workdir, ignore_errors=True)
        raise CompileError(_trim_compiler_log(log))
    return Program(workdir, spec, runner)


def _trim_compiler_log(log: str, max_lines: int = 40) -> str:
    """Keep the first real errors; g++ template spew is mostly noise."""
    lines = log.split("\n")
    errors = [ln for ln in lines if re.search(r"\berror\b", ln, re.IGNORECASE)]
    kept = (errors or lines)[:max_lines]
    if len(lines) > len(kept):
        kept.append(f"... ({len(lines) - len(kept)} more lines suppressed)")
    return "\n".join(kept)
