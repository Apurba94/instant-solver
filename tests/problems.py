"""Real problem statements used by the test suite.

These are written in the style of Codeforces / CSES statements rather than
copied from any site, so the suite tests the parser against realistic prose
(unicode maths, prose constraints, embedded samples) without reproducing
anyone's problem text.
"""

MAX_SUBARRAY = {
    "title": "Maximum Subarray Sum",
    "statement": """Maximum Subarray Sum

Time limit: 1 second
Memory limit: 256 MB

You are given an array of n integers. Your task is to find the maximum sum of
values in a contiguous, non-empty subarray.

Input
The first line contains an integer n: the size of the array.
The second line contains n integers a_1, a_2, ..., a_n: the contents of the array.

Output
Print one integer: the maximum subarray sum.

Constraints
1 <= n <= 2*10^5
-10^9 <= a_i <= 10^9
""",
    "sample_input": "8\n-1 3 -2 5 3 -5 2 2",
    "sample_output": "9",
}

LIS = {
    "title": "Increasing Subsequence",
    "statement": """Increasing Subsequence

Time limit: 1 second
Memory limit: 512 MB

You are given an array containing n integers. Your task is to determine the
longest increasing subsequence in the array, i.e., the longest subsequence
where every element is strictly larger than the previous one.

Input
The first line contains an integer n.
The second line contains n integers x_1, x_2, ..., x_n.

Output
Print the length of the longest increasing subsequence.

Constraints
1 <= n <= 2*10^5
1 <= x_i <= 10^9
""",
    "sample_input": "8\n7 3 5 3 6 2 9 8",
    "sample_output": "4",
}

DIJKSTRA = {
    "title": "Shortest Routes",
    "statement": """Shortest Routes

Time limit: 2 seconds
Memory limit: 512 MB

There are n cities and m roads between them. Each road has a length. Your task
is to determine the shortest path from city 1 to every city.

Input
The first line contains two integers n and m: the number of cities and roads.
Then there are m lines describing the roads. Each line has three integers u, v
and w: there is a road between cities u and v whose length is w.

Output
Print n integers: the shortest path lengths from city 1 to every city. If a city
cannot be reached, print -1 for it.

Constraints
1 <= n <= 10^5
1 <= m <= 2*10^5
1 <= u, v <= n
1 <= w <= 10^9
""",
    "sample_input": "4 4\n1 2 7\n1 3 9\n2 3 10\n3 4 2",
    "sample_output": "0 7 9 11",
}

SPLIT_ARRAY = {
    "title": "Fair Workload",
    "statement": """Fair Workload

Time limit: 1 second
Memory limit: 256 MB

An array of n positive integers must be split into at most k contiguous,
non-empty parts. The cost of a split is the largest sum among its parts.
Minimise the maximum part sum.

Input
The first line contains two integers n and k.
The second line contains n integers a_1, ..., a_n.

Output
Print the minimum possible largest part sum.

Constraints
1 <= k <= n <= 10^5
1 <= a_i <= 10^9
""",
    "sample_input": "5 2\n7 2 5 10 8",
    "sample_output": "18",
}

COMPONENTS = {
    "title": "Building Roads",
    "statement": """Building Roads

Time limit: 1 second
Memory limit: 512 MB

There are n cities and m roads. Two cities are in the same connected component
if you can travel from one to the other. Count the number of connected
components in the graph.

Input
The first line contains two integers n and m.
Then there are m lines describing the roads; each contains two integers u and v.

Output
Print the number of connected components.

Constraints
1 <= n <= 10^5
1 <= m <= 2*10^5
""",
    "sample_input": "5 3\n1 2\n3 4\n2 3",
    "sample_output": "2",
}

PRIMES = {
    "title": "Counting Primes",
    "statement": """Counting Primes

Time limit: 1 second
Memory limit: 256 MB

Given an integer n, count how many prime numbers are less than or equal to n.

Input
A single integer n.

Output
Print the number of primes not exceeding n.

Constraints
0 <= n <= 10^7
""",
    "sample_input": "20",
    "sample_output": "8",
}

# Uses unicode maths and prose constraints on purpose, to exercise the parser.
UNICODE_PARSE = {
    "title": "Pair Sum",
    "statement": """Pair Sum

time limit per test: 2 seconds
memory limit per test: 256 megabytes

You are given an array of n integers and a target value. Determine whether two
distinct elements of the array sum to exactly the target.

Input
The first line contains two integers n and target.
The second line contains n integers.

Output
Print YES if such a pair exists and NO otherwise.

Constraints
1 ≤ n ≤ 2·10⁵
1 ≤ a_i ≤ 10⁹
The value of target does not exceed 2·10⁹.
""",
    "sample_input": "4 9\n2 7 11 15",
    "sample_output": "YES",
}

# Deliberately not in the corpus, to test graceful failure.
UNKNOWN = {
    "title": "Chromatic Polynomial Evaluation",
    "statement": """Chromatic Polynomial Evaluation

Given a graph, evaluate its chromatic polynomial at the point q = 7 modulo a
prime, where the graph is given as an incidence structure over a finite field.

Constraints
1 <= n <= 18
""",
    "sample_input": "1\n0",
    "sample_output": "7",
}

ALL = {
    "max_subarray": MAX_SUBARRAY,
    "lis": LIS,
    "dijkstra": DIJKSTRA,
    "split_array": SPLIT_ARRAY,
    "components": COMPONENTS,
    "primes": PRIMES,
    "unicode_parse": UNICODE_PARSE,
}
