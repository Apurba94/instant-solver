"""The archetype corpus.

Two jobs, one dataset:

1. **Retrieval.** In production this is the first thing the pipeline consults.
   A large share of what people paste into a solver is a standard problem
   wearing a costume, and matching it against a curated archetype is faster,
   cheaper and more reliable than reasoning from scratch every time.

2. **Offline operation.** The corpus lets the whole engine — compile, judge,
   stress-test, explain — run and be tested with no API key and no network,
   which is what makes the pipeline itself testable in CI.

Each archetype carries a matcher, a plan, a fast solution, an independent brute
force, a random generator and a full editorial. The brute force is written to
share none of the fast solution's reasoning: that independence is the entire
point of differential testing.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Archetype:
    key: str
    title: str
    signals: list[str]                    # regex fragments scored against the statement
    required: list[str] = field(default_factory=list)   # all must appear
    technique: str = ""
    why: str = ""
    steps: list[str] = field(default_factory=list)
    time_complexity: str = ""
    space_complexity: str = ""
    risks: list[str] = field(default_factory=list)
    solution_cpp: str = ""
    brute_cpp: str = ""
    generator_py: str = ""
    explanation: dict = field(default_factory=dict)


# --------------------------------------------------------------------------

CORPUS: list[Archetype] = [

    Archetype(
        key="max_subarray",
        title="Maximum subarray sum (Kadane's algorithm)",
        signals=[r"maximum (?:sum|possible sum)", r"contiguous", r"subarray",
                 r"consecutive elements", r"largest sum"],
        required=[r"subarray|contiguous|consecutive"],
        technique="Kadane's algorithm — one linear scan carrying the best suffix sum",
        why=("Trying every subarray is O(n^2), which dies at n = 10^5. The observation that "
             "the best subarray ending at position i is either the element alone or that "
             "element appended to the best subarray ending at i-1 collapses it to O(n)."),
        steps=[
            "Keep `best_ending_here`, the largest sum of a subarray that ends exactly at the current index.",
            "At each element x, set best_ending_here = max(x, best_ending_here + x) — either start fresh at x, or extend.",
            "Keep a running `best_overall` = max(best_overall, best_ending_here).",
            "Initialise best_overall to the first element, not to 0, so all-negative arrays are handled.",
        ],
        time_complexity="O(n)",
        space_complexity="O(1)",
        risks=["An all-negative array must return the largest single element, not 0.",
               "Sums of 10^5 values up to 10^9 overflow 32-bit int."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;

    long long best_overall = LLONG_MIN;   // answer over all subarrays
    long long best_ending_here = 0;       // best sum of a subarray ending at i

    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        // Either extend the previous best suffix, or start a new subarray at x.
        best_ending_here = max(x, best_ending_here + x);
        best_overall = max(best_overall, best_ending_here);
    }

    cout << best_overall << "\n";
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;

// Oracle: try literally every (l, r) pair and sum it. O(n^3), obviously correct.
int main() {
    int n;
    if (!(cin >> n)) return 0;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;

    long long best = LLONG_MIN;
    for (int l = 0; l < n; ++l)
        for (int r = l; r < n; ++r) {
            long long s = 0;
            for (int k = l; k <= r; ++k) s += a[k];
            best = max(best, s);
        }
    cout << best << "\n";
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
n = random.randint(1, 8)
print(n)
# Negative values on purpose: the all-negative case is where naive code breaks.
print(*[random.randint(-10, 10) for _ in range(n)])
""",
        explanation={
            "intuition": (
                "The brute force asks 'what is the best subarray?' and checks all O(n^2) of them. "
                "The trick is to ask a smaller question instead: 'what is the best subarray that "
                "ends exactly here?' That version has only n answers, and each one follows from the "
                "previous in constant time — because a subarray ending at i is either just a[i], or "
                "a subarray ending at i-1 with a[i] glued on. The moment you see that, the problem "
                "is linear."
            ),
            "observations": [
                "Any subarray ending at index i is either the single element a[i], or (a subarray ending at i-1) + a[i].",
                "So the best subarray ending at i depends only on the best subarray ending at i-1, not on all of them.",
                "The global answer is the maximum over all i of 'best subarray ending at i', because every subarray ends somewhere.",
            ],
            "approach": (
                "Sweep left to right holding one number, best_ending_here. At each element decide "
                "whether the running subarray is worth keeping: if the accumulated sum has gone "
                "negative it can only hurt whatever comes next, so we drop it and start again at the "
                "current element. Track the largest value best_ending_here ever reaches."
            ),
            "algorithm_steps": [
                "Read n and then the array, processing each value as it arrives — nothing needs to be stored.",
                "Maintain best_ending_here, the maximum sum of a subarray ending at the current position.",
                "For each x: best_ending_here = max(x, best_ending_here + x).",
                "Maintain best_overall = max(best_overall, best_ending_here).",
                "Print best_overall.",
            ],
            "correctness": (
                "Induction on i. Claim: after processing index i, best_ending_here holds the maximum "
                "sum over all subarrays ending at i. Base case i = 0: the only such subarray is {a[0]}, "
                "and max(a[0], 0 + a[0]) = a[0]. Inductive step: any subarray ending at i is either the "
                "single element a[i], or some subarray ending at i-1 extended by a[i]. The best of the "
                "second kind is exactly best_ending_here(i-1) + a[i], since adding the same a[i] to every "
                "candidate preserves their order. Taking the max of the two cases gives the claim. "
                "Every subarray ends at exactly one index, so maximising over i covers all of them."
            ),
            "time_complexity": "O(n)",
            "space_complexity": "O(1)",
            "complexity_justification": (
                "One pass, constant work per element, and only two scalars are kept — the array itself "
                "never has to be stored. At n = 10^5 that is roughly 10^5 operations, which is four "
                "orders of magnitude inside a 1-second budget."
            ),
            "code_walkthrough": [
                {"lines": "sync_with_stdio / cin.tie",
                 "what": "Unties C++ streams from C stdio. On large inputs this alone is often the difference between passing and a time limit."},
                {"lines": "best_overall = LLONG_MIN",
                 "what": "Starting at the smallest possible value, not 0, is what makes all-negative arrays come out right. Initialising to 0 silently returns 0 — the single most common bug in this problem."},
                {"lines": "best_ending_here = max(x, best_ending_here + x)",
                 "what": "The whole algorithm. 'Start fresh at x' versus 'extend what I had'. No array indexing is needed because only the previous value matters."},
                {"lines": "long long throughout",
                 "what": "10^5 elements of magnitude 10^9 sum to 10^14, which overflows a 32-bit int about ten thousand times over."},
            ],
            "dry_run": [
                {"step": "Start, before reading any element", "state": "best_ending_here = 0, best_overall = -infinity"},
                {"step": "x = -2: max(-2, 0 + -2) = -2", "state": "best_ending_here = -2, best_overall = -2"},
                {"step": "x = 1: max(1, -2 + 1 = -1) = 1 — the negative prefix is dropped", "state": "best_ending_here = 1, best_overall = 1"},
                {"step": "x = -3: max(-3, 1 + -3 = -2) = -2", "state": "best_ending_here = -2, best_overall = 1"},
                {"step": "x = 4: max(4, -2 + 4 = 2) = 4 — dropped again", "state": "best_ending_here = 4, best_overall = 4"},
                {"step": "x = -1: max(-1, 4 + -1 = 3) = 3", "state": "best_ending_here = 3, best_overall = 4"},
                {"step": "x = 2: max(2, 3 + 2 = 5) = 5", "state": "best_ending_here = 5, best_overall = 5"},
                {"step": "x = 1: max(1, 5 + 1 = 6) = 6", "state": "best_ending_here = 6, best_overall = 6"},
                {"step": "x = -5: max(-5, 6 + -5 = 1) = 1", "state": "best_ending_here = 1, best_overall = 6"},
                {"step": "x = 4: max(4, 1 + 4 = 5) = 5", "state": "best_ending_here = 5, best_overall = 6 — final answer 6, the subarray [4, -1, 2, 1]"},
            ],
            "pitfalls": [
                "Initialising the answer to 0. On an all-negative array the correct answer is the largest single element; starting at 0 returns 0 and fails the hidden tests while passing every friendly sample.",
                "Using int for the sum. n = 10^5 and |a_i| = 10^9 gives sums up to 10^14.",
                "Resetting best_ending_here to 0 instead of to x when it goes negative — subtly different, and wrong when every element is negative.",
                "Forgetting that the subarray must be non-empty when the statement says so.",
            ],
            "alternatives": [
                "Prefix sums: answer = max over r of (prefix[r] - min prefix[l] for l < r). Also O(n), and it generalises better to 'subarray with sum closest to K'.",
                "Divide and conquer: solve left half, right half, and the crossing case. O(n log n) — strictly worse here, but it is the version that extends to a segment tree when the array is updated between queries.",
                "Segment tree storing (total, best prefix, best suffix, best subarray) per node: O(log n) per update and query. The right answer when the problem adds modifications.",
            ],
            "related_topics": ["Prefix sums", "Dynamic programming on prefixes",
                               "Divide and conquer", "Segment tree with merge information",
                               "Maximum subarray with at most k changes"],
            "why_this_works_here": (
                "The constraint n <= 10^5 rules out the O(n^2) double loop but leaves enormous room "
                "for a single linear pass, and the problem has the optimal-substructure property that "
                "makes that pass possible."
            ),
        },
    ),

    Archetype(
        key="lis",
        title="Longest increasing subsequence",
        signals=[r"longest increasing subsequence", r"strictly increasing",
                 r"longest.{0,20}subsequence", r"\blis\b"],
        required=[r"subsequence"],
        technique="Patience sorting — binary search over the array of smallest tail values",
        why=("The textbook O(n^2) DP is fine to n = 5000 and hopeless at n = 2*10^5. Keeping only "
             "the smallest possible tail for each achievable length makes that array sorted, which "
             "turns each transition into a binary search and gives O(n log n)."),
        steps=[
            "Maintain `tails`, where tails[k] is the smallest value that can end an increasing subsequence of length k+1.",
            "tails is automatically strictly increasing, so it can be binary searched.",
            "For each x, find the first position with tails[pos] >= x (lower_bound for strict increase).",
            "Overwrite tails[pos] with x, or append x if pos is past the end.",
            "The answer is the final length of tails.",
        ],
        time_complexity="O(n log n)",
        space_complexity="O(n)",
        risks=["lower_bound gives strictly increasing; upper_bound gives non-decreasing. Read the statement carefully.",
               "tails is NOT the LIS itself — only its length is meaningful without extra bookkeeping."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;

    // tails[k] = smallest value that can end an increasing subsequence of length k+1.
    vector<long long> tails;
    tails.reserve(n);

    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        // lower_bound => strictly increasing. Use upper_bound for non-decreasing.
        auto it = lower_bound(tails.begin(), tails.end(), x);
        if (it == tails.end()) tails.push_back(x);   // x extends the longest run
        else *it = x;                                 // x is a better tail for that length
    }

    cout << tails.size() << "\n";
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;

// Oracle: the O(n^2) definition-following DP. dp[i] = LIS ending exactly at i.
int main() {
    int n;
    if (!(cin >> n)) return 0;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;

    int best = 0;
    vector<int> dp(n, 1);
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < i; ++j)
            if (a[j] < a[i]) dp[i] = max(dp[i], dp[j] + 1);
        best = max(best, dp[i]);
    }
    cout << best << "\n";
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
n = random.randint(1, 8)
print(n)
# A tiny value range forces lots of equal elements, which is exactly where the
# strict-vs-non-strict distinction (lower_bound vs upper_bound) shows up.
print(*[random.randint(1, 6) for _ in range(n)])
""",
        explanation={
            "intuition": (
                "The O(n^2) DP asks, for every element, 'which earlier smaller element should I extend?' "
                "That question is expensive because it scans everything before i. Flip it around: for each "
                "possible LENGTH, what is the smallest value that can end a subsequence of that length? "
                "Being greedy about tails is always safe — a smaller tail can be extended by strictly more "
                "future elements and never by fewer. And because those best tails are sorted, you can binary "
                "search them. n <= 2*10^5 with an O(n log n) budget is practically a signpost pointing at "
                "'sort or binary search', which is what should make you look for this reformulation."
            ),
            "observations": [
                "For a fixed length k, only the smallest achievable ending value matters — any subsequence with a larger tail is dominated.",
                "The array of best tails is strictly increasing, so it supports binary search.",
                "Each new element either extends the longest run (append) or improves the tail for exactly one length (overwrite). Never both.",
                "The length of the tails array is the LIS length at every point in the scan.",
            ],
            "approach": (
                "Process elements left to right, maintaining the tails array. For x, binary search for the "
                "first tail that is >= x. If none exists, x is larger than every tail and extends the longest "
                "subsequence found so far, so append it. Otherwise x is a strictly better ending value for "
                "that length, so overwrite it. The array's length at the end is the answer."
            ),
            "algorithm_steps": [
                "Start with an empty tails array.",
                "For each element x, binary search tails for the first entry >= x (lower_bound).",
                "If the search runs off the end, push x — the longest subsequence just grew by one.",
                "Otherwise overwrite that entry with x — same length, better (smaller) tail.",
                "Print tails.size().",
            ],
            "correctness": (
                "Invariant: after processing a prefix, tails[k] is the minimum over all increasing "
                "subsequences of length k+1 in that prefix of their final element, and tails is strictly "
                "increasing. Strict monotonicity holds because a length-(k+1) subsequence's prefix of "
                "length k is itself increasing and ends at a strictly smaller value, so tails[k-1] < tails[k]. "
                "When x arrives, the longest subsequence it can extend is the largest k with tails[k] < x, "
                "which is exactly the position before lower_bound(x); writing x at lower_bound's position "
                "records a length-(that+1) subsequence ending at x. It is a minimum because any other "
                "subsequence of that length ending at x would have had a tail at least as large. "
                "Overwriting never loses a solution: the displaced value was larger and therefore dominated."
            ),
            "time_complexity": "O(n log n)",
            "space_complexity": "O(n)",
            "complexity_justification": (
                "One binary search per element over an array of at most n entries: n log n ~ 2*10^5 * 18 "
                "~ 3.6*10^6 operations, comfortably inside a 1-2 second limit. The O(n^2) DP would be "
                "4*10^10 — about four hours."
            ),
            "code_walkthrough": [
                {"lines": "vector<long long> tails; tails.reserve(n);",
                 "what": "Reserving up front avoids reallocation during the scan. A small constant-factor win that matters at 2*10^5."},
                {"lines": "lower_bound(tails.begin(), tails.end(), x)",
                 "what": "Finds the first tail >= x. This is the strict-increase variant. For a non-decreasing LIS you would use upper_bound — a one-word change that flips the answer on arrays with duplicates."},
                {"lines": "if (it == tails.end()) push_back else *it = x",
                 "what": "Append when x beats every tail, otherwise improve one tail in place. Exactly one of the two happens per element, which is why the whole scan is linear in the number of writes."},
                {"lines": "cout << tails.size()",
                 "what": "The array's contents are NOT the LIS — the values can be a mix from different subsequences. Only the size is meaningful. Recovering the actual subsequence needs a parent-pointer array."},
            ],
            "dry_run": [
                {"step": "x = 3: tails empty, append", "state": "tails = [3]"},
                {"step": "x = 1: lower_bound finds 3 at index 0, overwrite", "state": "tails = [1] — same length, smaller tail"},
                {"step": "x = 4: larger than everything, append", "state": "tails = [1, 4]"},
                {"step": "x = 1: lower_bound finds 1 at index 0, overwrite with 1", "state": "tails = [1, 4] — no change"},
                {"step": "x = 5: append", "state": "tails = [1, 4, 5]"},
                {"step": "x = 9: append", "state": "tails = [1, 4, 5, 9]"},
                {"step": "x = 2: lower_bound finds 4 at index 1, overwrite", "state": "tails = [1, 2, 5, 9] — length 2 now ends at 2 instead of 4"},
                {"step": "x = 6: lower_bound finds 9 at index 3, overwrite", "state": "tails = [1, 2, 5, 6]"},
                {"step": "x = 5: lower_bound finds 5 at index 2, overwrite with 5", "state": "tails = [1, 2, 5, 6] — final size 4, answer 4"},
            ],
            "pitfalls": [
                "Using upper_bound when the statement says strictly increasing (or lower_bound when it says non-decreasing). Both compile, both look right, and they differ on every array with duplicates.",
                "Printing the tails array as if it were the subsequence. It is not — its entries can come from different subsequences and may not even be a subsequence of the input.",
                "Assuming the O(n^2) DP will pass because it passed the samples. At n = 2*10^5 it is roughly four hours of compute.",
                "Forgetting n = 0 or n = 1 when the statement permits them.",
            ],
            "alternatives": [
                "O(n^2) DP: dp[i] = 1 + max(dp[j] for j < i with a[j] < a[i]). Simpler and easier to modify, fine to about n = 5000, and the right choice when you also need the subsequence itself with minimal code.",
                "Fenwick tree over coordinate-compressed values, querying the max dp on a value prefix: also O(n log n), and it generalises to weighted LIS or to 'longest chain in 2D' where patience sorting alone does not.",
                "For the actual subsequence, store for each element the position it occupied in tails plus a parent index, then walk backwards from the last append. Still O(n log n), O(n) extra memory.",
            ],
            "related_topics": ["Binary search on a sorted structure", "Patience sorting",
                               "Fenwick tree for prefix maxima", "Dilworth's theorem",
                               "Longest common subsequence", "Russian doll envelopes (2D LIS)"],
            "why_this_works_here": (
                "n <= 2*10^5 permits O(n log n) and forbids O(n^2), and the tails reformulation is the "
                "standard way to buy that log factor."
            ),
        },
    ),

    Archetype(
        key="dijkstra",
        title="Single-source shortest path with non-negative weights",
        signals=[r"shortest path", r"minimum (?:time|cost|distance)",
                 r"weighted.{0,20}(?:graph|edges)", r"roads?", r"\bdijkstra\b"],
        required=[r"path|road|edge|graph"],
        technique="Dijkstra's algorithm with a binary heap",
        why=("Edge weights are non-negative, which is exactly Dijkstra's precondition. BFS would be "
             "wrong because edges have differing costs; Bellman-Ford is O(V*E) and unnecessary "
             "without negative edges; Floyd-Warshall is O(V^3) and answers a question nobody asked."),
        steps=[
            "Build an adjacency list of (neighbour, weight) pairs.",
            "Set dist[source] = 0 and every other distance to infinity.",
            "Push (0, source) into a min-heap keyed by distance.",
            "Pop the smallest-distance vertex; skip it if the popped distance is stale (greater than dist[v]).",
            "Relax each outgoing edge: if dist[v] + w < dist[u], update dist[u] and push (dist[u], u).",
            "Print the distances, using -1 for vertices that stay at infinity.",
        ],
        time_complexity="O((V + E) log V)",
        space_complexity="O(V + E)",
        risks=["Distances up to V * maxWeight overflow 32-bit int.",
               "Lazy deletion is required: check the popped distance against dist[v] or the heap grows unbounded.",
               "Unreachable vertices need an explicit sentinel in the output."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;
using ll = long long;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) return 0;

    vector<vector<pair<int, ll>>> adj(n + 1);
    for (int i = 0; i < m; ++i) {
        int u, v; ll w;
        cin >> u >> v >> w;
        adj[u].push_back({v, w});
        adj[v].push_back({u, w});     // undirected; drop this line for a directed graph
    }

    const ll INF = LLONG_MAX / 4;
    vector<ll> dist(n + 1, INF);
    dist[1] = 0;

    // Min-heap of (distance, vertex). greater<> makes pop() return the smallest.
    priority_queue<pair<ll, int>, vector<pair<ll, int>>, greater<>> pq;
    pq.push({0, 1});

    while (!pq.empty()) {
        auto [d, v] = pq.top();
        pq.pop();
        if (d > dist[v]) continue;    // stale entry left behind by an earlier improvement
        for (auto [u, w] : adj[v]) {
            if (d + w < dist[u]) {
                dist[u] = d + w;
                pq.push({dist[u], u});
            }
        }
    }

    for (int v = 1; v <= n; ++v)
        cout << (dist[v] == INF ? -1 : dist[v]) << " \n"[v == n];
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;
using ll = long long;

// Oracle: Bellman-Ford. Relax every edge V-1 times. O(V*E), no heap, no greedy
// argument -- it shares none of Dijkstra's reasoning, which is the point.
int main() {
    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<array<ll, 3>> edges;
    for (int i = 0; i < m; ++i) {
        ll u, v, w;
        cin >> u >> v >> w;
        edges.push_back({u, v, w});
        edges.push_back({v, u, w});
    }
    const ll INF = LLONG_MAX / 4;
    vector<ll> dist(n + 1, INF);
    dist[1] = 0;
    for (int it = 0; it < n; ++it)
        for (auto &e : edges)
            if (dist[e[0]] < INF && dist[e[0]] + e[2] < dist[e[1]])
                dist[e[1]] = dist[e[0]] + e[2];
    for (int v = 1; v <= n; ++v)
        cout << (dist[v] == INF ? -1 : dist[v]) << " \n"[v == n];
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
n = random.randint(2, 6)
# Allow disconnected graphs on purpose: unreachable vertices are a classic bug.
max_edges = n * (n - 1) // 2
m = random.randint(0, min(max_edges, 8))
pairs = [(u, v) for u in range(1, n + 1) for v in range(u + 1, n + 1)]
random.shuffle(pairs)
chosen = pairs[:m]
print(n, len(chosen))
for u, v in chosen:
    print(u, v, random.randint(1, 10))
""",
        explanation={
            "intuition": (
                "Dijkstra is greedy, and the greed is justified by one fact: with non-negative weights, "
                "the closest unfinalised vertex can never be improved by going through a vertex that is "
                "farther away — any such detour is already at least as long before it even continues. So "
                "the moment a vertex is popped with the smallest tentative distance, that distance is final. "
                "The heap exists purely to find that closest vertex quickly. The signal to reach for this is "
                "'shortest path' plus 'weights, all non-negative'; if any weight could be negative the "
                "greedy argument collapses and you need Bellman-Ford."
            ),
            "observations": [
                "With non-negative weights, the smallest tentative distance in the frontier is already optimal and can be finalised.",
                "Each edge only ever needs to be relaxed from its already-finalised endpoint, so every edge is processed O(1) times.",
                "A binary heap turns 'find the closest unfinalised vertex' from O(V) into O(log V), which is what makes the whole thing near-linear.",
            ],
            "approach": (
                "Build an adjacency list, put the source in a min-heap at distance 0, then repeatedly pop "
                "the closest vertex and relax its outgoing edges, pushing improved neighbours back into the "
                "heap. Because a vertex can be pushed several times, discard any pop whose recorded distance "
                "is worse than the best known — that lazy deletion is simpler and faster than trying to "
                "decrease keys inside the heap."
            ),
            "algorithm_steps": [
                "Read the graph into an adjacency list of (neighbour, weight).",
                "Initialise all distances to infinity, and the source to 0.",
                "Push (0, source) onto a min-heap ordered by distance.",
                "While the heap is non-empty, pop (d, v); if d > dist[v] the entry is stale, so skip it.",
                "For each edge (v, u, w), if d + w < dist[u], set dist[u] = d + w and push (dist[u], u).",
                "Output every distance, printing a sentinel for vertices still at infinity.",
            ],
            "correctness": (
                "Claim: when a vertex v is popped with d == dist[v], dist[v] is the true shortest distance. "
                "Suppose not, and let v be the first popped vertex whose distance is wrong. The true shortest "
                "path to v leaves the finalised set at some edge (x, y) where x is finalised and y is not. "
                "Since x was popped earlier and (by minimality of v) correctly, dist[y] <= dist[x] + w(x,y), "
                "which is at most the true distance to v because the remainder of the path has non-negative "
                "length. Then y would have been popped before v, contradicting the choice of v. The "
                "non-negativity is load-bearing: with a negative edge, the remainder of the path could reduce "
                "the total and the contradiction disappears."
            ),
            "time_complexity": "O((V + E) log V)",
            "space_complexity": "O(V + E)",
            "complexity_justification": (
                "Each edge causes at most one heap push, so the heap holds O(E) entries and each push and "
                "pop costs O(log E) = O(log V) for a simple graph. At V = 10^5 and E = 2*10^5 that is a few "
                "million operations."
            ),
            "code_walkthrough": [
                {"lines": "adj[u].push_back({v, w}); adj[v].push_back({u, w});",
                 "what": "Both directions, because the graph is undirected. Deleting the second line makes this a directed-graph solver — worth checking against the statement, as it is a silent source of wrong answers."},
                {"lines": "const ll INF = LLONG_MAX / 4;",
                 "what": "Dividing by 4 leaves headroom so INF + w does not overflow during a relaxation test. Using LLONG_MAX directly wraps to a negative number and every unreachable vertex suddenly looks close."},
                {"lines": "priority_queue<..., greater<>>",
                 "what": "C++'s priority_queue is a max-heap by default; greater<> inverts it. Forgetting this yields a longest-path-ish traversal that still terminates and still prints numbers."},
                {"lines": "if (d > dist[v]) continue;",
                 "what": "Lazy deletion. A vertex can sit in the heap several times at different distances; only the smallest is meaningful. Without this line the algorithm is still correct but re-expands vertices and degrades badly on dense graphs."},
                {"lines": "\" \\n\"[v == n]",
                 "what": "A compact idiom: prints a space between values and a newline after the last. Equivalent to an if, and common in contest code."},
            ],
            "dry_run": [
                {"step": "Graph 1-2 (w 7), 1-3 (w 9), 2-3 (w 10), 3-4 (w 2). Push (0,1)", "state": "dist = [0, inf, inf, inf], heap = {(0,1)}"},
                {"step": "Pop (0,1). Relax 1->2 (7) and 1->3 (9)", "state": "dist = [0, 7, 9, inf], heap = {(7,2), (9,3)}"},
                {"step": "Pop (7,2). Relax 2->3: 7 + 10 = 17, not better than 9, so no update", "state": "dist = [0, 7, 9, inf], heap = {(9,3)}"},
                {"step": "Pop (9,3). Relax 3->4: 9 + 2 = 11 < inf", "state": "dist = [0, 7, 9, 11], heap = {(11,4)}"},
                {"step": "Pop (11,4). No outgoing edges left to improve", "state": "heap empty; final distances 0 7 9 11"},
            ],
            "pitfalls": [
                "Using int for distances. V = 10^5 vertices and weights of 10^9 give paths up to 10^14.",
                "Setting INF to LLONG_MAX, so that INF + w overflows during relaxation and produces a negative 'distance' that wins every comparison.",
                "Omitting the stale-entry check, which lets the heap grow and vertices be re-expanded.",
                "Running Dijkstra on a graph with negative edges. It gives a plausible wrong answer rather than an error — use Bellman-Ford or SPFA there.",
                "Printing 0 instead of a sentinel for unreachable vertices, which reads as 'distance zero'.",
            ],
            "alternatives": [
                "0-1 BFS with a deque when every weight is 0 or 1: O(V + E) with no heap at all.",
                "Bellman-Ford, O(V*E): slower, but the only option with negative edges, and it detects negative cycles.",
                "Floyd-Warshall, O(V^3): the right tool when you need all pairs and V <= 500.",
                "Dijkstra with a Fibonacci heap: O(E + V log V) in theory, essentially never worth the constant factor in a contest.",
            ],
            "related_topics": ["Graph traversal (BFS/DFS)", "0-1 BFS", "Bellman-Ford",
                               "Floyd-Warshall", "A* search", "Minimum spanning tree",
                               "Shortest path DAG / counting shortest paths"],
            "why_this_works_here": (
                "Non-negative weights make the greedy finalisation sound, and V, E around 10^5 put "
                "O((V + E) log V) comfortably inside the limit while ruling out anything quadratic."
            ),
        },
    ),

    Archetype(
        key="binary_search_answer",
        title="Binary search on the answer",
        signals=[r"minimi[sz]e the maximum", r"maximi[sz]e the minimum",
                 r"smallest .{0,25} such that", r"largest .{0,25} such that",
                 r"minimum possible (?:largest|maximum)", r"at least k", r"split.{0,20}into"],
        required=[r"minim|maxim"],
        technique="Binary search over the answer with a monotone feasibility check",
        why=("The answer is an integer in a known range, and feasibility is monotone: if a budget of "
             "X works then so does any larger budget. That monotonicity is what a binary search "
             "needs, and it converts an impossible search over configurations into log(range) calls "
             "to a simple linear check."),
        steps=[
            "Identify the answer's search range [lo, hi] — usually max(element) to sum(elements).",
            "Write feasible(X): can the goal be met when the limit is X? It must be monotone in X.",
            "Binary search the smallest X with feasible(X) true.",
            "Return that X.",
        ],
        time_complexity="O(n log(sum))",
        space_complexity="O(n)",
        risks=["The feasibility check must be monotone or binary search is meaningless.",
               "lo must start at max(a) — a single element can never be split.",
               "mid = lo + (hi - lo) / 2 avoids overflow when both are near the 64-bit limit."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;
using ll = long long;

int n, k;
vector<ll> a;

// Can the array be cut into at most k contiguous pieces, each summing to <= limit?
// Greedy is optimal here: extend the current piece as far as possible, because
// cutting earlier can never reduce the number of pieces needed.
bool feasible(ll limit) {
    int pieces = 1;
    ll current = 0;
    for (ll x : a) {
        if (x > limit) return false;          // one element alone already exceeds it
        if (current + x > limit) { ++pieces; current = x; }
        else current += x;
    }
    return pieces <= k;
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    if (!(cin >> n >> k)) return 0;
    a.resize(n);
    ll lo = 0, hi = 0;
    for (auto &x : a) { cin >> x; lo = max(lo, x); hi += x; }

    // Invariant: feasible(hi) is true, feasible(lo - 1) is false.
    while (lo < hi) {
        ll mid = lo + (hi - lo) / 2;          // written this way to avoid overflow
        if (feasible(mid)) hi = mid;
        else lo = mid + 1;
    }
    cout << lo << "\n";
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;
using ll = long long;

// Oracle: try every possible set of cut positions by brute force over bitmasks.
// Exponential and completely uninsightful -- exactly what a good oracle is.
int main() {
    int n, k;
    if (!(cin >> n >> k)) return 0;
    vector<ll> a(n);
    for (auto &x : a) cin >> x;

    ll best = LLONG_MAX;
    // Bit i set means "cut after element i". n-1 possible cut positions.
    for (int mask = 0; mask < (1 << max(0, n - 1)); ++mask) {
        int pieces = __builtin_popcount(mask) + 1;
        if (pieces > k) continue;
        ll worst = 0, cur = 0;
        for (int i = 0; i < n; ++i) {
            cur += a[i];
            if (i < n - 1 && (mask >> i & 1)) { worst = max(worst, cur); cur = 0; }
        }
        worst = max(worst, cur);
        best = min(best, worst);
    }
    cout << best << "\n";
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
n = random.randint(1, 7)
k = random.randint(1, n)
print(n, k)
print(*[random.randint(1, 12) for _ in range(n)])
""",
        explanation={
            "intuition": (
                "Searching directly over ways to split the array is hopeless — there are 2^(n-1) of them. "
                "But notice the shape of the question: 'minimise the maximum'. That phrasing is almost always "
                "a signal to stop searching for the arrangement and start searching for the ANSWER instead. "
                "Guess a value X and ask the much easier yes/no question 'can it be done with every piece at "
                "most X?'. That check is a simple greedy sweep, and because a larger X is never harder, the "
                "answers form a monotone false...false,true...true pattern — precisely what binary search needs."
            ),
            "observations": [
                "Feasibility is monotone: if a limit of X works, every limit above X works too.",
                "So the set of feasible limits is a suffix of the integer range, and its first element is the answer.",
                "Checking one candidate limit is a linear greedy sweep: keep adding to the current piece until it would overflow, then start a new one.",
                "The answer lies between max(a) (one element cannot be split) and sum(a) (a single piece).",
            ],
            "approach": (
                "Binary search the smallest feasible limit. Each step calls a greedy feasibility check that "
                "walks the array once, counting how many pieces the limit forces. Roughly 40 iterations of a "
                "linear check settle a range as wide as 10^14."
            ),
            "algorithm_steps": [
                "Compute lo = max(a) and hi = sum(a).",
                "While lo < hi: take mid, and if feasible(mid) move hi down to mid, otherwise move lo up to mid + 1.",
                "feasible(X): sweep the array greedily, starting a new piece whenever adding the next element would exceed X; report whether the piece count is within k.",
                "Print lo.",
            ],
            "correctness": (
                "Two parts. First, the greedy check is optimal: extending the current piece as long as it fits "
                "never increases the number of pieces, since any solution that cuts earlier can be transformed "
                "into the greedy one by moving cuts later without ever creating a piece that exceeds X — a "
                "standard exchange argument. Second, the search is valid because feasible is monotone: a piece "
                "assignment valid for limit X is still valid for any X' > X, so feasible(X) implies "
                "feasible(X'). The loop maintains the invariant that the answer lies in [lo, hi], and halving "
                "the range each step terminates at the smallest feasible value."
            ),
            "time_complexity": "O(n log(sum of a))",
            "space_complexity": "O(n)",
            "complexity_justification": (
                "The range has width at most sum(a) <= 10^14, so about 47 iterations, each an O(n) sweep. "
                "At n = 10^5 that is under 5*10^6 operations."
            ),
            "code_walkthrough": [
                {"lines": "if (x > limit) return false;",
                 "what": "An element larger than the limit can never be placed, no matter how many pieces are allowed. Missing this line makes the greedy loop silently produce nonsense for small limits."},
                {"lines": "lo = max(lo, x); hi += x;",
                 "what": "Sets the search bounds from the data. Starting lo at 0 instead of max(a) still works here only because the x > limit guard rejects those values — but it wastes iterations and hides the reasoning."},
                {"lines": "ll mid = lo + (hi - lo) / 2;",
                 "what": "The overflow-safe midpoint. (lo + hi) / 2 overflows when both are near 9*10^18; this form never does."},
                {"lines": "if (feasible(mid)) hi = mid; else lo = mid + 1;",
                 "what": "The 'find the first true' pattern. hi = mid rather than mid - 1, because mid itself may be the answer. Getting this wrong by one is the most common way to hang the loop or return a neighbour of the answer."},
            ],
            "dry_run": [
                {"step": "Input n=5, k=2, a=[7, 2, 5, 10, 8]. lo = 10, hi = 32", "state": "search range [10, 32]"},
                {"step": "mid = 21: pieces [7,2,5] = 14, then [10,8] = 18 -> 2 pieces <= 2, feasible", "state": "hi = 21"},
                {"step": "mid = 15: [7,2,5] = 14, then [10] = 10, then [8] -> 3 pieces > 2, not feasible", "state": "lo = 16"},
                {"step": "mid = 18: [7,2,5] = 14, then [10,8] = 18 -> 2 pieces, feasible", "state": "hi = 18"},
                {"step": "mid = 17: [7,2,5] = 14, then [10] = 10, then [8] -> 3 pieces, not feasible", "state": "lo = 18"},
                {"step": "lo == hi == 18, loop ends", "state": "answer 18, the split [7,2,5] and [10,8]"},
            ],
            "pitfalls": [
                "Binary searching a predicate that is not actually monotone. Then the search converges to a meaningless value; always state the monotonicity out loud before writing the loop.",
                "The classic off-by-one: hi = mid - 1 when looking for the first true value skips the answer. Fix the invariant on paper first.",
                "(lo + hi) / 2 overflowing on 64-bit ranges.",
                "Forgetting that a single element larger than the limit makes the whole limit infeasible.",
                "Searching over floating-point values without a fixed iteration count — use 100 iterations or an epsilon, never lo < hi on doubles.",
            ],
            "alternatives": [
                "DP over (prefix, pieces used) computing the minimum possible maximum: O(n^2 k), exact and easier to justify, fine for small n and the right choice when the pieces have to be reported.",
                "Parametric search / Lagrangian relaxation (the Aliens trick) when k is large and the cost as a function of piece count is convex.",
                "Greedy alone, without the search, does not work: there is no direct way to place k-1 cuts optimally in one pass.",
            ],
            "related_topics": ["Binary search on the answer", "Monotone predicates",
                               "Greedy exchange arguments", "Parametric search",
                               "Ternary search on unimodal functions", "Aliens trick"],
            "why_this_works_here": (
                "The answer is an integer in a bounded range and the feasibility test is monotone and linear, "
                "so log(range) sweeps settle it while any direct search over splits is exponential."
            ),
        },
    ),

    Archetype(
        key="dsu_components",
        title="Connected components with a disjoint set union",
        signals=[r"connected component", r"how many groups", r"friend circles",
                 r"same\b.{0,20}\b(?:group|set|component)", r"\bmerge\b", r"islands",
                 r"number of (?:connected )?components?", r"travel from",
                 r"count the number of (?:connected )?components?"],
        required=[r"component|group|connect|island|merge"],
        technique="Disjoint Set Union with path compression and union by size",
        why=("Repeated 'are these two in the same group?' and 'merge these groups' queries are "
             "exactly what DSU is for. With both optimisations each operation is effectively "
             "constant time, where a naive relabelling scan would be O(n) per merge."),
        steps=[
            "Give every element its own set, with parent[i] = i and size[i] = 1.",
            "find(x) walks to the representative, rewriting parents to point straight at the root (path compression).",
            "unite(a, b) attaches the smaller tree under the larger (union by size), keeping depth logarithmic even before compression.",
            "Process every edge as a unite, counting successful merges.",
            "Components = n - number of successful merges.",
        ],
        time_complexity="O((n + m) alpha(n)), effectively linear",
        space_complexity="O(n)",
        risks=["Union without size/rank degrades to a linked list and O(n) finds.",
               "1-indexed input into a 0-indexed array is the classic off-by-one here.",
               "Counting merges is safer than recounting distinct roots at the end."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;

struct DSU {
    vector<int> parent, size_;
    explicit DSU(int n) : parent(n + 1), size_(n + 1, 1) {
        iota(parent.begin(), parent.end(), 0);
    }
    int find(int x) {
        while (parent[x] != x) {
            parent[x] = parent[parent[x]];   // path halving: compress as we walk
            x = parent[x];
        }
        return x;
    }
    bool unite(int a, int b) {
        a = find(a); b = find(b);
        if (a == b) return false;            // already together
        if (size_[a] < size_[b]) swap(a, b); // attach smaller under larger
        parent[b] = a;
        size_[a] += size_[b];
        return true;
    }
};

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n, m;
    if (!(cin >> n >> m)) return 0;

    DSU dsu(n);
    int components = n;                      // every vertex starts alone
    for (int i = 0; i < m; ++i) {
        int u, v;
        cin >> u >> v;
        if (dsu.unite(u, v)) --components;   // a real merge removes one component
    }

    cout << components << "\n";
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;

// Oracle: plain BFS flood fill over an adjacency list. No union-find reasoning
// at all -- it just walks the graph and counts how many times it had to restart.
int main() {
    int n, m;
    if (!(cin >> n >> m)) return 0;
    vector<vector<int>> adj(n + 1);
    for (int i = 0; i < m; ++i) {
        int u, v; cin >> u >> v;
        adj[u].push_back(v);
        adj[v].push_back(u);
    }
    vector<bool> seen(n + 1, false);
    int components = 0;
    for (int s = 1; s <= n; ++s) {
        if (seen[s]) continue;
        ++components;
        queue<int> q; q.push(s); seen[s] = true;
        while (!q.empty()) {
            int v = q.front(); q.pop();
            for (int u : adj[v]) if (!seen[u]) { seen[u] = true; q.push(u); }
        }
    }
    cout << components << "\n";
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
n = random.randint(1, 7)
m = random.randint(0, 8)
print(n, m)
for _ in range(m):
    # Self-loops and duplicate edges are allowed on purpose -- both must be no-ops.
    print(random.randint(1, n), random.randint(1, n))
""",
        explanation={
            "intuition": (
                "The question 'how many groups are there?' only ever needs one fact about each element: "
                "which group it belongs to. DSU stores that as a forest where each tree is a group and the "
                "root is the group's name. Merging two groups is then a single pointer write. The counting "
                "trick is even simpler than it looks — you never have to count groups at the end. Start at n "
                "groups, and every edge that actually joins two different groups reduces the count by exactly "
                "one."
            ),
            "observations": [
                "Connectivity is an equivalence relation, so the elements partition into disjoint classes — exactly what DSU represents.",
                "An edge inside an existing component changes nothing; only edges between components matter.",
                "Each successful merge reduces the component count by exactly one, so the answer is n minus the number of successful merges.",
                "Path compression plus union by size makes the amortised cost the inverse Ackermann function, which is at most 4 for any input that fits in memory.",
            ],
            "approach": (
                "Initialise every vertex as its own component. For each edge, find both endpoints' roots; if "
                "they differ, attach the smaller tree under the larger and decrement the component count. "
                "Path halving inside find flattens the tree as a side effect of every query."
            ),
            "algorithm_steps": [
                "parent[i] = i and size[i] = 1 for all i; components = n.",
                "For each edge (u, v), compute find(u) and find(v).",
                "If the roots are equal, skip — the edge is redundant.",
                "Otherwise attach the smaller-sized root under the larger, add the sizes, and decrement components.",
                "Print components.",
            ],
            "correctness": (
                "Invariant: at every point, two vertices have the same root exactly when they are connected "
                "by edges processed so far. It holds initially (no edges, every vertex its own root) and is "
                "preserved by unite, which merges precisely the two classes containing the edge's endpoints "
                "and touches no others. Union by size keeps every tree's depth at most log n, because a "
                "vertex's depth only increases when its tree is attached under a tree at least as large, "
                "which at least doubles its component's size — so that can happen at most log n times. Path "
                "halving only shortens paths and never changes which root a vertex reaches, so it cannot "
                "affect correctness."
            ),
            "time_complexity": "O((n + m) * alpha(n)), effectively O(n + m)",
            "space_complexity": "O(n)",
            "complexity_justification": (
                "Two arrays of n integers, and one near-constant find per edge endpoint. The inverse "
                "Ackermann function alpha(n) is below 5 for n up to 10^600, so it is a constant in practice."
            ),
            "code_walkthrough": [
                {"lines": "iota(parent.begin(), parent.end(), 0)",
                 "what": "Fills parent with 0, 1, 2, ... so every element starts as its own root. Sized n+1 to allow 1-indexed vertices directly, which removes a whole class of off-by-one bugs."},
                {"lines": "parent[x] = parent[parent[x]]; x = parent[x];",
                 "what": "Path halving: every step re-points a node at its grandparent. It gives the same amortised bound as full path compression with no recursion, so it cannot overflow the stack on a degenerate chain."},
                {"lines": "if (size_[a] < size_[b]) swap(a, b);",
                 "what": "Union by size. Without it, repeatedly attaching a big tree under a small one builds a linked list and finds degrade to O(n)."},
                {"lines": "if (dsu.unite(u, v)) --components;",
                 "what": "unite returns whether a real merge happened, so the count stays right without a second pass. Redundant edges and self-loops fall out automatically as no-ops."},
            ],
            "dry_run": [
                {"step": "n = 5, edges (1,2), (3,4), (2,3), (1,3). Start", "state": "parent = [0,1,2,3,4,5], components = 5"},
                {"step": "Edge (1,2): roots 1 and 2 differ, merge", "state": "parent[2] = 1, size[1] = 2, components = 4"},
                {"step": "Edge (3,4): roots 3 and 4 differ, merge", "state": "parent[4] = 3, size[3] = 2, components = 3"},
                {"step": "Edge (2,3): find(2) = 1, find(3) = 3, sizes equal so 1 absorbs 3", "state": "parent[3] = 1, size[1] = 4, components = 2"},
                {"step": "Edge (1,3): find(1) = 1, find(3) = 1 — already together, no-op", "state": "components = 2 — final answer 2, namely {1,2,3,4} and {5}"},
            ],
            "pitfalls": [
                "Omitting union by size or rank. It still works, but a chain of merges builds a path and finds become O(n) — enough to time out at 10^5.",
                "Recursive find on a degenerate structure blowing the stack. Iterative path halving avoids it entirely.",
                "Allocating n instead of n+1 entries for 1-indexed vertices.",
                "Counting distinct roots at the end with a loop over find(i) — correct, but easy to get wrong when the loop bounds and indexing disagree. Counting merges is simpler.",
                "Reaching for DSU when edges are also deleted. DSU cannot undo a union; that needs rollback DSU with no path compression, or an offline divide-and-conquer.",
            ],
            "alternatives": [
                "BFS or DFS flood fill: O(n + m), just as fast here, and it also gives you each component's members for free. Prefer it when the graph is static and given up front.",
                "DSU with rollback (union by size only, no path compression) plus offline divide and conquer, for problems where edges appear and disappear over time.",
                "Weighted / bipartite DSU, which stores the parity of the path to the root and answers 'are these two in opposite groups?'.",
            ],
            "related_topics": ["Disjoint Set Union", "Kruskal's MST algorithm", "Graph traversal",
                               "Small-to-large merging", "Offline dynamic connectivity",
                               "Bipartite checking with weighted DSU"],
            "why_this_works_here": (
                "The graph is only ever grown, never cut, which is exactly the regime where DSU's "
                "near-constant merges apply."
            ),
        },
    ),

    Archetype(
        key="sieve_primes",
        title="Prime sieve",
        signals=[r"\bprimes?\b", r"sieve", r"number of primes", r"prime factor"],
        required=[r"prime"],
        technique="Sieve of Eratosthenes",
        why=("Testing each number to sqrt(n) individually costs O(n sqrt n), which is far too slow "
             "past 10^6. The sieve marks composites through their multiples instead, and the "
             "harmonic series makes the total work O(n log log n) — essentially linear."),
        steps=[
            "Allocate a boolean array of size n+1, initially all true.",
            "Mark 0 and 1 as not prime.",
            "For each i from 2 while i*i <= n, if i is still prime, mark i*i, i*i+i, i*i+2i, ... as composite.",
            "Starting at i*i is safe: every smaller multiple already has a smaller prime factor.",
            "Read off the answer from the array.",
        ],
        time_complexity="O(n log log n)",
        space_complexity="O(n) bytes, or O(n/8) with a bitset",
        risks=["i*i overflows 32-bit int when n is near 2*10^9 — use long long or compare i <= n/i.",
               "Starting the inner loop at 2*i instead of i*i wastes about half the work.",
               "A vector<bool> is bit-packed and slower per access than a vector<char>."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) return 0;
    if (n < 2) { cout << 0 << "\n"; return 0; }

    // vector<char> rather than vector<bool>: not bit-packed, noticeably faster.
    vector<char> is_prime(n + 1, 1);
    is_prime[0] = is_prime[1] = 0;

    for (long long i = 2; i * i <= n; ++i) {
        if (!is_prime[i]) continue;
        // Start at i*i: any smaller multiple of i has a prime factor below i
        // and was already crossed out then.
        for (long long j = i * i; j <= n; j += i) is_prime[j] = 0;
    }

    int count = 0;
    for (int i = 2; i <= n; ++i) count += is_prime[i];
    cout << count << "\n";
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;

// Oracle: trial division on every number, straight from the definition of prime.
int main() {
    int n;
    if (!(cin >> n)) return 0;
    int count = 0;
    for (int x = 2; x <= n; ++x) {
        bool prime = true;
        for (int d = 2; d < x; ++d)
            if (x % d == 0) { prime = false; break; }
        count += prime;
    }
    cout << count << "\n";
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
# Small values keep the O(n^2) oracle fast, and include 0 and 1 as edge cases.
print(random.randint(0, 60))
""",
        explanation={
            "intuition": (
                "Asking 'is x prime?' for each x separately throws away everything learned from the "
                "previous numbers. Flip the direction: instead of looking for each number's divisors, let "
                "each prime announce its own multiples as composite. Every composite has a prime factor, so "
                "every composite gets announced at least once, and what remains untouched is exactly the "
                "primes. The cost is the sum of n/p over primes p, which is O(n log log n) — for practical "
                "purposes, linear."
            ),
            "observations": [
                "Every composite number has at least one prime factor no larger than its square root, so sieving only up to sqrt(n) suffices.",
                "When the sieve reaches prime i, every multiple of i below i*i already has a smaller prime factor and has been crossed out — so the inner loop can start at i*i.",
                "The total work is n * sum(1/p over primes p <= n), and that sum grows like log log n.",
            ],
            "approach": (
                "Allocate a flag per number, assume everything is prime, then for each prime found in "
                "increasing order cross out its multiples starting from its square. Count what survives."
            ),
            "algorithm_steps": [
                "Create is_prime[0..n], all true; set indices 0 and 1 to false.",
                "For i = 2 while i*i <= n: if is_prime[i], mark every j = i*i, i*i + i, ... up to n as false.",
                "Count the surviving true entries from 2 to n.",
            ],
            "correctness": (
                "Claim: after the sieve, is_prime[x] is true exactly when x is prime. If x is composite, "
                "write x = p * q with p its smallest prime factor; then p <= sqrt(x) <= sqrt(n), so the outer "
                "loop reaches p, and p is still marked prime at that moment (nothing smaller divides it). "
                "Since q >= p, we have x = p*q >= p*p, so x is at or after the inner loop's start and is a "
                "multiple of p — it gets crossed out. Conversely a prime has no factor other than 1 and "
                "itself, so it is never a multiple of any smaller i and is never crossed out."
            ),
            "time_complexity": "O(n log log n)",
            "space_complexity": "O(n)",
            "complexity_justification": (
                "The inner loop runs n/p times for each prime p <= sqrt(n). Summing n/p over primes gives "
                "n * log log n by Mertens' theorem. At n = 10^7 that is a few tens of millions of byte "
                "writes — well under a second."
            ),
            "code_walkthrough": [
                {"lines": "vector<char> is_prime(n + 1, 1)",
                 "what": "vector<char>, not vector<bool>. The latter packs into bits, so every access costs a shift and a mask; for a sieve that is a measurable slowdown despite using 8x less memory."},
                {"lines": "for (long long i = 2; i * i <= n; ++i)",
                 "what": "i is long long so i*i cannot overflow. With int and n near 2*10^9, i*i wraps negative and the loop condition silently becomes true forever."},
                {"lines": "for (long long j = i * i; j <= n; j += i)",
                 "what": "Starting at i*i rather than 2*i. Both are correct; this one skips work already done by smaller primes and is a solid constant-factor win."},
                {"lines": "count += is_prime[i]",
                 "what": "Relies on char-to-int promotion of 0/1. Clear and branch-free."},
            ],
            "dry_run": [
                {"step": "n = 20. Initialise all true, clear 0 and 1", "state": "primes so far: 2..20 all candidates"},
                {"step": "i = 2 is prime. Cross out 4, 6, 8, 10, 12, 14, 16, 18, 20", "state": "remaining: 2,3,5,7,9,11,13,15,17,19"},
                {"step": "i = 3 is prime. Cross out 9, 12, 15, 18 (12 and 18 already gone)", "state": "remaining: 2,3,5,7,11,13,17,19"},
                {"step": "i = 4: 4*4 = 16 <= 20 but is_prime[4] is false, skip", "state": "unchanged"},
                {"step": "i = 5: 5*5 = 25 > 20, loop ends", "state": "8 primes below 20 — answer 8"},
            ],
            "pitfalls": [
                "Forgetting that 0 and 1 are not prime. The array starts all-true and these two must be cleared explicitly.",
                "int overflow in i*i for large n. Use long long, or write the condition as i <= n / i.",
                "Sieving to n instead of sqrt(n) in the outer loop — correct but slower than it needs to be.",
                "Using vector<bool> in a hot sieve and paying the bit-packing cost on every write.",
                "Re-running the sieve inside a multi-test loop instead of computing it once before reading the tests.",
            ],
            "alternatives": [
                "Linear sieve (Euler's sieve): O(n) exactly, and it yields each number's smallest prime factor, which makes factorisation O(log n) per query. The right choice when you need factorisations, not just primality.",
                "Segmented sieve: sieves an interval [L, R] with R up to 10^12 using only O(sqrt(R)) memory. The standard answer to 'count primes between L and R'.",
                "Miller-Rabin: deterministic for 64-bit inputs with a fixed witness set, and the only option when a single enormous number must be tested.",
                "Trial division to sqrt(x): perfectly fine for one number, hopeless for a whole range.",
            ],
            "related_topics": ["Number theory", "Linear sieve and smallest prime factor",
                               "Segmented sieve", "Miller-Rabin primality test", "Pollard's rho",
                               "Euler totient via sieve", "Mobius function"],
            "why_this_works_here": (
                "The problem asks about a whole range of numbers at once, which is exactly when amortising "
                "the work across the range beats testing each one alone."
            ),
        },
    ),

    Archetype(
        key="two_sum",
        title="Find a pair summing to a target",
        signals=[r"two numbers", r"sum(?:s)? to\b.{0,20}\b(?:target|given|value|k|x)",
                 r"pair.{0,25}sum", r"\btwo sum\b", r"two distinct elements",
                 r"exactly\b.{0,15}\b(?:target|k|x)", r"\btarget\b",
                 r"whether two", r"sum to exactly"],
        required=[r"pair|two"],
        technique="Single-pass hash set of complements",
        why=("Checking every pair is O(n^2). Storing what has been seen turns 'does a partner exist?' "
             "into a hash lookup, so one pass over the array is enough."),
        steps=[
            "Walk the array once, keeping a hash set of values already seen.",
            "For each x, ask whether target - x is in the set.",
            "If it is, a valid pair exists; otherwise insert x and continue.",
            "Checking before inserting is what prevents pairing an element with itself.",
        ],
        time_complexity="O(n) expected",
        space_complexity="O(n)",
        risks=["Insert after the lookup, never before, or x pairs with itself.",
               "target - x can overflow when both are near the 32-bit limit.",
               "unordered_set can be forced into O(n) per operation by adversarial input; on Codeforces use a custom hash or sort plus two pointers."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    long long target;
    if (!(cin >> n >> target)) return 0;

    unordered_set<long long> seen;
    seen.reserve(n * 2);
    seen.max_load_factor(0.7f);

    for (int i = 0; i < n; ++i) {
        long long x;
        cin >> x;
        // Look BEFORE inserting, so x cannot be paired with itself.
        if (seen.count(target - x)) { cout << "YES\n"; return 0; }
        seen.insert(x);
    }

    cout << "NO\n";
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;

// Oracle: every pair, straight from the definition.
int main() {
    int n; long long target;
    if (!(cin >> n >> target)) return 0;
    vector<long long> a(n);
    for (auto &x : a) cin >> x;
    for (int i = 0; i < n; ++i)
        for (int j = i + 1; j < n; ++j)
            if (a[i] + a[j] == target) { cout << "YES\n"; return 0; }
    cout << "NO\n";
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
n = random.randint(1, 8)
# A small value range guarantees plenty of hits, duplicates, and the
# x + x == target case that catches self-pairing bugs.
print(n, random.randint(2, 20))
print(*[random.randint(1, 10) for _ in range(n)])
""",
        explanation={
            "intuition": (
                "The double loop asks, for every element, 'is my partner anywhere in the array?' — and "
                "re-scans to find out. But partners are symmetric: if x and y pair up, then when you reach "
                "the later of the two, the earlier one has already gone past. So remember what you have "
                "seen, and each element only has to ask one question: 'have I already met target - x?' A "
                "hash set answers that in expected constant time."
            ),
            "observations": [
                "For any valid pair, one element comes second; checking only backwards is therefore enough to find every pair.",
                "The question 'does value v exist among the elements seen so far?' is exactly a hash-set membership test.",
                "Querying before inserting the current element is what stops x from being its own partner when target = 2x.",
            ],
            "approach": (
                "One pass. Keep a set of values seen so far. For each new x, look up target - x; a hit means "
                "a pair exists. Otherwise add x and move on."
            ),
            "algorithm_steps": [
                "Create an empty hash set and reserve capacity to avoid rehashing.",
                "For each element x: if target - x is in the set, report success.",
                "Otherwise insert x.",
                "If the loop finishes, no pair exists.",
            ],
            "correctness": (
                "If a valid pair (i, j) with i < j exists, then when the scan reaches j the value a[i] is "
                "already in the set (it was inserted at step i, and nothing is removed), so the lookup for "
                "target - a[j] = a[i] succeeds and the algorithm reports success no later than j. Conversely, "
                "a reported success at step j means target - a[j] was inserted at some earlier step i < j, so "
                "a[i] + a[j] = target genuinely holds. Since the lookup precedes the insertion, i is strictly "
                "less than j and the two are distinct positions."
            ),
            "time_complexity": "O(n) expected, O(n^2) worst case with an adversarial hash",
            "space_complexity": "O(n)",
            "complexity_justification": (
                "One hash insert and one lookup per element, each expected O(1). The worst case only "
                "materialises when someone deliberately constructs colliding keys, which on Codeforces is a "
                "real and regularly exploited attack."
            ),
            "code_walkthrough": [
                {"lines": "seen.reserve(n * 2); seen.max_load_factor(0.7f);",
                 "what": "Pre-sizing the table avoids repeated rehashing during the scan — often a 2-3x speedup on large inputs."},
                {"lines": "if (seen.count(target - x))",
                 "what": "The lookup happens before the insert. Swapping those two lines makes the program answer YES for any single element with 2x == target, which is the classic bug in this problem."},
                {"lines": "long long throughout",
                 "what": "target - x is computed in 64 bits, so values near the 32-bit boundary cannot wrap and produce a phantom match."},
            ],
            "dry_run": [
                {"step": "a = [2, 7, 11, 15], target = 9. Start", "state": "seen = {}"},
                {"step": "x = 2: is 9 - 2 = 7 in seen? No. Insert 2", "state": "seen = {2}"},
                {"step": "x = 7: is 9 - 7 = 2 in seen? Yes", "state": "pair (2, 7) found — print YES and stop"},
            ],
            "pitfalls": [
                "Inserting before looking up, which lets an element pair with itself.",
                "Using a plain unordered_set on Codeforces, where hand-crafted anti-hash tests turn it into O(n^2). Add a randomised hash or use sort plus two pointers.",
                "32-bit overflow in target - x.",
                "Assuming values are distinct. If the answer must be indices and duplicates exist, store value -> index in a map and handle the duplicate case explicitly.",
            ],
            "alternatives": [
                "Sort, then two pointers from both ends: O(n log n), no hashing, immune to anti-hash tests, and it generalises directly to counting pairs or finding the closest sum.",
                "Sort plus binary search for each complement: O(n log n), the natural choice when the array is already sorted.",
                "A frequency array when values are small and bounded: O(n + maxValue) with no hashing at all.",
            ],
            "related_topics": ["Hashing", "Two pointers", "Sorting", "3-sum and k-sum",
                               "Meet in the middle", "Anti-hash tests and custom hash functions"],
            "why_this_works_here": (
                "Only existence is asked for, and order does not matter, so a single backward-looking pass "
                "with a membership structure is enough."
            ),
        },
    ),

    Archetype(
        key="a_plus_b",
        title="Read and combine a small fixed number of values",
        signals=[r"^\s*(?:given )?two integers", r"sum of (?:the )?two", r"a \+ b",
                 r"print their sum"],
        required=[r"sum|add"],
        technique="Direct computation",
        why="There is no algorithmic content; the work is reading input and printing the result.",
        steps=["Read the values.", "Compute the result.", "Print it."],
        time_complexity="O(1)",
        space_complexity="O(1)",
        risks=["Values near 10^18 overflow even 64-bit when added — check the stated bounds."],
        solution_cpp=r"""#include <bits/stdc++.h>
using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(nullptr);

    long long a, b;
    if (!(cin >> a >> b)) return 0;
    cout << a + b << "\n";
    return 0;
}
""",
        brute_cpp=r"""#include <bits/stdc++.h>
using namespace std;
int main() {
    long long a, b;
    if (!(cin >> a >> b)) return 0;
    // Deliberately different route to the same answer: increment b times.
    long long result = a;
    long long steps = llabs(b);
    if (steps > 2000000) { cout << a + b << "\n"; return 0; }
    for (long long i = 0; i < steps; ++i) result += (b > 0 ? 1 : -1);
    cout << result << "\n";
    return 0;
}
""",
        generator_py="""import random, sys
if len(sys.argv) > 1:
    random.seed(int(sys.argv[1]))
print(random.randint(-1000, 1000), random.randint(-1000, 1000))
""",
        explanation={
            "intuition": "Read the two numbers and print their sum. The only decision is the integer type.",
            "observations": [
                "The stated bounds decide the type: values up to 10^9 fit in int, sums of them do not fit comfortably, and anything larger needs 64-bit.",
            ],
            "approach": "Read both values into 64-bit integers and print the sum.",
            "algorithm_steps": ["Read a and b.", "Print a + b."],
            "correctness": "Addition is exact in 64-bit integer arithmetic for the stated range.",
            "time_complexity": "O(1)",
            "space_complexity": "O(1)",
            "complexity_justification": "A fixed amount of work regardless of the values.",
            "code_walkthrough": [
                {"lines": "long long a, b;",
                 "what": "Chosen over int so the sum cannot overflow for inputs up to about 4.6*10^18."},
                {"lines": "if (!(cin >> a >> b)) return 0;",
                 "what": "Guards against malformed or empty input instead of using uninitialised values."},
            ],
            "dry_run": [
                {"step": "Read a = 3, b = 4", "state": "a = 3, b = 4"},
                {"step": "Print a + b", "state": "output 7"},
            ],
            "pitfalls": [
                "Using int when the bounds allow 10^18.",
                "Printing a trailing space or extra blank line when the judge does an exact match.",
            ],
            "alternatives": ["scanf/printf instead of streams — equivalent here, marginally faster at scale."],
            "related_topics": ["Fast I/O", "Integer overflow", "64-bit arithmetic"],
            "why_this_works_here": "There is no structure to exploit; the direct computation is optimal.",
        },
    ),
]


CORPUS_BY_KEY = {arch.key: arch for arch in CORPUS}
