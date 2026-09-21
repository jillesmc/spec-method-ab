# User Stories: kvstore

Canonical behavior catalog for kvstore. Companion to `_spec.md`; consumed by `_spec.md` Part II
(component mapping) and `_tests.md` (coverage matrix). There is no UI surface, so no `_uiux.md`.

## Personas

- **Serviço** — the unattended process that owns the state directory. It writes configuration, counters
  and a processing position, answers "gravei" to its own callers, and is restarted several times a day by
  deploys and OOM kills. It needs the ack to be unconditional.
- **Operador** — the engineer who inspects or repairs the state from a shell, usually right after an
  incident, usually in a hurry. They need line-oriented output, exit codes they can branch on, and error
  messages that say what to do.
- **Integrador** — the developer of the Serviço, wiring kvstore into its code. They choose between the
  CLI and the Python API and need both to carry the same guarantee.

## Story Index

| ID     | Feature Area          | Persona     | Story                                                          |
| ------ | --------------------- | ----------- | -------------------------------------------------------------- |
| US-001 | Basic operations      | Serviço     | Write a value and be told it is on disk                         |
| US-002 | Basic operations      | Operador    | Read a key back exactly as written                              |
| US-003 | Basic operations      | Operador    | Delete a key and know whether it existed                        |
| US-004 | Basic operations      | Operador    | List every key that currently exists                            |
| US-005 | Survives restart      | Serviço     | Keep every acknowledged write across a restart or a kill        |
| US-006 | Survives restart      | Operador    | Open the directory after a crash without a repair step          |
| US-007 | Concurrency           | Operador    | Touch the directory while the service is running, safely        |
| US-008 | Growth and size       | Serviço     | Store large values and keep writing forever without cleanup     |
| US-009 | Embedding             | Integrador  | Use the same store in-process with the same guarantee           |

## Basic operations

### US-001: Write a value and be told it is on disk

**As a** Serviço, **I want** a write to report success only once it is durable, **so that** the "gravei" I
answer to my own callers is true even if I die one instant later.

Acceptance criteria:

- AC-1: Given a directory that does not exist yet, when I run `python -m kvstore ./dados set posicao 42`,
  then the directory and its database are created, stdout is empty, and the exit code is 0.
- AC-2: Given `posicao` already holds `42`, when I set it to `43`, then a later `get posicao` returns `43`
  and no trace of `42` is readable through any verb.
- AC-3: Given any successful `set`, when the process is killed with SIGKILL the instant it exits, then a
  new process reads the value that was set.

Edge cases:

- EC-1: Empty key (`set "" valor`) → rejected as a usage error with exit code 2; nothing is written and
  the directory is not created.
- EC-2: Key containing a newline or a NUL character → rejected as a usage error with exit code 2, because
  `list` is line-oriented and such a key could not be listed unambiguously.
- EC-3: Value containing newlines, tabs, NUL, or non-ASCII text → stored and returned byte for byte.
- EC-4: Empty value (`set chave ""`) → accepted; `get` returns nothing and the key appears in `list`.
- EC-5: Value too large to pass as an argument → `set chave -` reads the value from stdin and stores it
  identically.
- EC-6: The given path exists but is a regular file, not a directory → exit code 3 with a message naming
  the path; nothing is written.
- EC-7: The directory exists but is not writable → exit code 3 with the operating-system reason; no
  partial state is left behind.
- EC-8: The same `set chave valor` repeated → the second call is observably a no-op; `get` and `list` are
  unchanged.

### US-002: Read a key back exactly as written

**As an** Operador, **I want** `get` to print the stored value and nothing else, **so that** I can pipe it
into another command or compare it without stripping bytes the store added.

Acceptance criteria:

- AC-1: Given `modo` holds `rapido`, when I run `get modo`, then stdout is exactly `rapido` with no
  trailing newline added, and the exit code is 0.
- AC-2: Given a value that ends in a newline, when I `get` it, then stdout ends with exactly that one
  newline — the round trip `set` → `get` never adds or removes a byte.

Edge cases:

- EC-1: Key that was never written → exit code 1, a one-line message on stderr, and empty stdout.
- EC-2: Key that was deleted → same as EC-1.
- EC-3: `get` against a directory that does not exist → exit code 1 (an empty store has no keys), and the
  directory is **not** created, so a typo'd path does not leave litter behind.

### US-003: Delete a key and know whether it existed

**As an** Operador, **I want** `del` to tell me whether the key was there, **so that** a cleanup script can
distinguish "removed it" from "it was already gone" without a preceding `get`.

Acceptance criteria:

- AC-1: Given `obsoleta` exists, when I run `del obsoleta`, then the exit code is 0, stdout is empty, the
  key is absent from `list`, and `get obsoleta` exits 1.
- AC-2: Given the deletion returned, when the process is killed immediately, then the key is still absent
  after a restart — deletes are as durable as writes.

Edge cases:

- EC-1: `del` on a key that does not exist → exit code 1 with a message on stderr; the store is unchanged.
- EC-2: `del` on the same key twice → the first exits 0, the second exits 1; the on-disk result of both
  sequences is identical.

### US-004: List every key that currently exists

**As an** Operador, **I want** one key per line in a stable order, **so that** I can diff two listings and
feed the output to `grep`, `wc` or a loop.

Acceptance criteria:

- AC-1: Given keys `b`, `a`, `c` were written in that order, when I run `list`, then stdout is `a`, `b`,
  `c`, one per line, each terminated by a newline, exit code 0.
- AC-2: Given a key was deleted, when I run `list`, then that key is absent and every other key remains.

Edge cases:

- EC-1: Empty store, or a directory that does not exist → no output at all, exit code 0.
- EC-2: Keys containing spaces or non-ASCII characters → printed verbatim, one per line.
- EC-3: 100 000 keys → all of them are listed, in order, without loading any value.

## Survives restart

### US-005: Keep every acknowledged write across a restart or a kill

**As a** Serviço, **I want** the store's content after any restart to be exactly the set of writes that
were acknowledged, **so that** a deploy or an OOM kill costs me nothing I already promised.

Acceptance criteria:

- AC-1: Given a child process that sets a key and is sent SIGKILL as soon as the set returns, when a new
  process opens the same directory, then the value is there.
- AC-2: Given fifty keys written and acknowledged, when the writer is killed and a new process opens the
  directory, then all fifty are present with their exact values.
- AC-3: Given the store has never been closed cleanly, when it is opened again, then it opens without any
  manual repair, flag, or recovery command.

Edge cases:

- EC-1: The writer is killed in the middle of writing a large value → the interrupted write is absent,
  every previously acknowledged key is intact, and the store opens normally.
- EC-2: Kill-and-reopen repeated many times in a row → no cumulative damage; the key set is exactly the
  acknowledged one after each cycle.
- EC-3: The process is killed between two of its own writes → the first is present, the second is absent;
  there is no state in which both are half-applied.

### US-006: Open the directory after a crash without a repair step

**As an** Operador, **I want** the store to be readable immediately after an abrupt kill, **so that** my
first command during an incident produces state instead of an error.

Acceptance criteria:

- AC-1: Given the directory contains the journal files left by a killed writer, when I run `list`, then it
  prints the keys and exits 0, with no extra step.
- AC-2: Given recovery happened, when I run `list` a second time, then the result is identical — recovery
  is not a one-shot side effect that changes what I see.

Edge cases:

- EC-1: The directory was written by a newer on-disk format version → refused with a message naming the
  version, exit code 3, and nothing in the directory is modified.
- EC-2: The directory contains an unrelated file (a note, an old backup) → kvstore neither reads, moves,
  nor deletes it, and the file is still there afterwards.
- EC-3: The database file is genuinely corrupt (not merely un-checkpointed) → a clear error and exit code
  3, never a silent empty store that would look like "we lost everything" all over again.

## Concurrency

### US-007: Touch the directory while the service is running, safely

**As an** Operador, **I want** my shell command against a live store to be safe, **so that** inspecting or
fixing a key during an incident cannot corrupt what the service is writing.

Acceptance criteria:

- AC-1: Given eight processes each setting a different key at the same time, when they all finish, then
  all eight keys are present with their exact values and the store is readable.
- AC-2: Given a writer is running, when I read concurrently, then my read returns either the old value or
  the new one, never a mixture and never an error.

Edge cases:

- EC-1: Another writer holds the write lock for longer than the timeout → exit code 3 with a "busy"
  message; nothing is written, and re-running works once the other writer is done.
- EC-2: Two processes set the same key concurrently → the final value is one of the two written values,
  never a blend of them.
- EC-3: A reader runs while the store is recovering a crashed writer's journal → the read succeeds and
  the reader makes no modification to the directory.

## Growth and size

### US-008: Store large values and keep writing forever without cleanup

**As a** Serviço, **I want** disk use to track what is actually stored rather than how many writes I have
ever done, **so that** nobody has to run a cleanup job that nobody would have run anyway.

Acceptance criteria:

- AC-1: Given a 64 MiB text value written from stdin, when I read it back, then it is byte-identical.
- AC-2: Given one key rewritten ten thousand times, when I look at the directory size, then it reflects
  one live value plus bounded journal overhead, not ten thousand values.
- AC-3: Given a write of any size, when it is performed, then its cost does not grow with the number of
  keys already in the store.

Edge cases:

- EC-1: Many keys written and then deleted → the space they used is reclaimed for later writes instead of
  accumulating forever.
- EC-2: Ten thousand consecutive writes in one long-lived process → the journal file stays bounded rather
  than growing with the write count.
- EC-3: 100 000 keys in the store → reading one key does not scan the others.

## Embedding

### US-009: Use the same store in-process with the same guarantee

**As an** Integrador, **I want** a small Python API with the same durability contract as the CLI,
**so that** the service can avoid spawning a process per write without weakening its promise.

Acceptance criteria:

- AC-1: Given `from kvstore import Store`, when I use `with Store("./dados") as s: s.set("k", "v")`, then
  the value is durable when `set` returns, exactly as with the CLI.
- AC-2: Given a missing key, when I call `s.get("ausente")`, then a `KeyNotFound` exception is raised
  rather than a sentinel value being returned.
- AC-3: Given the `with` block ends, when I inspect the directory, then the store is closed cleanly and
  the data written inside the block is all present.

Edge cases:

- EC-1: An exception raised inside the `with` block → the store still closes, and every write that
  returned before the exception is durable.
- EC-2: `Store` used without `with` and never closed, then the process is killed → every write that
  returned is still durable, because closing is not what makes writes durable.
- EC-3: Two `Store` objects opened on the same directory in one process → both work; writes from one are
  visible to the other's later reads.
