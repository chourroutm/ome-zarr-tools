# Phase 0 Research: Downsample and Upsample commands

## Decision: `downsample` reuses `ngff_zarr.to_multiscales()`; `upsample` is hand-built (no library support exists)

**Decision**: `downsample` wraps the existing dataset's coarsest level as an
`NgffImage` (via `nz.to_ngff_image()`, using that level's own scale from its
`coordinateTransformations`) and calls
`nz.to_multiscales(image, scale_factors=[2**i for i in range(1, n+1)])` for
`n` new levels — verified empirically: `scale_factors` as a plain list of
ints is **cumulative from the input image's own resolution**, not
per-level-incremental (`scale_factors=[2, 4]` produces two *different* levels
at 2x and 4x; `scale_factors=[2, 2]` produces two *identical* levels at 2x —
confirmed by direct testing). `ms.images[1:]` (skipping the echoed input at
index 0) are the `n` new levels to append. Default `method=None` resolves to
`Methods.ITKWASM_GAUSSIAN`, verified working in this environment.

`upsample` has **no equivalent** — grepped the entire installed `ngff_zarr`
package for `upsample`/`zoom`/`upscale`/`refine`: zero hits, and
`to_multiscales`'s own coarsening loop only ever multiplies scale factors
(never divides). Each new, finer level is instead built directly via
`dask.array.repeat(arr, 2, axis=i)` chained over every spatial axis — an
exact 2x nearest-neighbor expansion (each voxel becomes a 2x2x2 block of
itself). This is deliberately **not** `scipy.ndimage.zoom`/interpolation:
`.repeat()` can never produce a value that wasn't already in the source
array, which is what makes FR-009 ("never introducing fractional/
interpolated values") true *by construction* rather than by a post-hoc check.

**Rationale**: Reusing `to_multiscales()` for `downsample` avoids
reimplementing pyramid-building logic that already exists, is tested, and
already backs this codebase's own `migrate`. `upsample` genuinely has no
library equivalent to reuse, so the simplest operation that provably
satisfies "never interpolate label values" is used instead of a more
general-purpose (but riskier-for-labels) resize function.

**Alternatives considered**:
- *`upsample` via `skimage.transform.resize(..., order=0)`* (the same
  primitive `bioio_ome_zarr`'s own writer uses internally, per prior
  research) — rejected in favor of `dask.array.repeat`: for an exact integer
  scale factor of 2, both produce the identical result, but `repeat` is a
  pure array operation with no float/rounding path to reason about, and
  needs no extra import (`dask.array` is already a dependency; `repeat`
  keeps the result lazy, unlike `skimage.transform.resize` which forces a
  `map_blocks` wrapper to stay dask-native).
- *`downsample` via a hand-rolled block-mean/nearest reduction* (mirroring
  `upsample`'s hand-rolled approach for symmetry) — rejected: `to_multiscales`
  already exists, is already a dependency, and already backs this exact kind
  of operation elsewhere in this codebase (`migrate.py`) — reimplementing it
  would be pure duplication for no benefit.

## Decision: `upsample --smooth` = per-label-channel Gaussian smoothing + argmax re-snap

**Decision**: When `--smooth <sigma>` is given, each newly upsampled level is
(1) materialized to a NumPy array (`.compute()` — the smoothing kernel needs
cross-chunk neighbor context that plain `dask.array` block operations don't
give for free, and upsampled label levels are expected to be small enough for
this tool's scale), (2) split into one boolean channel per distinct label
value present, (3) each channel independently smoothed with
`scipy.ndimage.gaussian_filter(channel.astype(float), sigma)`, (4) the
per-voxel arg-max across channels picked as the new label. This generalizes
correctly to multi-label (not just binary) masks: naively Gaussian-blurring
the raw integer label array would treat label values as ordinal/numeric
(blurring between label `1` and label `5` could nonsensically produce label
`3`), which is wrong for categorical data — per-channel-then-argmax is the
standard correct technique for smoothing segmentations and reduces to
"blur-then-threshold-at-0.5" for the binary-mask case, so it isn't excess
complexity for the common case, just the correct generalization of it.

**Rationale**: Directly required by spec FR-010, resolved via
`/speckit-clarify`: smoothing must never leave a voxel with a non-discrete
value — argmax over per-label channels makes every output voxel exactly one
of the original label values, always.

**Alternatives considered**:
- *Blur the raw label array directly, then round* — rejected per
  clarification: produces nonsensical intermediate label values for any
  dataset with more than 2 label values (foreground/background), and even
  for the binary case, blur-then-round is mathematically identical to the
  chosen approach's degenerate case, so there's no simplicity actually
  gained by special-casing it.
- *Smooth lazily with a dask-native filter, keep everything out-of-core* —
  rejected: no dask-native Gaussian filter is available in this environment
  (`dask_image` — the package that would provide one — isn't installed here,
  and `ngff_zarr`'s own `Methods.DASK_IMAGE_*` options fail with
  `ModuleNotFoundError` for the same reason, verified empirically). Adding it
  as a new dependency for a single optional code path isn't justified when
  `scipy` (already a transitive, now-explicit dependency) covers it directly.

## Decision: `upsample`'s new finest level reorders the *metadata list only* — no existing array is renamed

**Decision**: New levels (both commands) get freshly chosen `path` strings —
the next unused integer beyond every existing `path` in the dataset (e.g.
existing `"0"`, `"1"` → new levels get `"2"`, `"3"`, ...) — regardless of
where they end up in the `datasets` list. `upsample` inserts its new
entries at the *front* of the `multiscales[0].datasets` list (so the new
finest level is `datasets[0]`, per this codebase's own finest-is-first
convention already relied on by `fix_metadata.py`/`ome_metadata.py`);
`downsample` appends its new entries at the *end*. In both cases, every
existing level's on-disk array keeps its original path/key untouched.

**Rationale**: Per the OME-NGFF spec (and confirmed directly against
`ome_zarr_models`' validator in this session), a dataset's `path` is an
arbitrary string identifier with no ordering meaning of its own — spec
compliance and "finest first" both come entirely from *list position*, not
from the string itself. Renaming/renumbering every existing level's on-disk
array just to keep path strings "looking sequential" would mean rewriting
every existing array (the exact whole-dataset-rewrite cost `downsample`/
`upsample` are designed to avoid, unlike `migrate`) for zero functional
benefit — the clarification session's own wording ("previous datasets[0]
shifts later in the list") already confirms this is about list position, not
the path string `"0"` specifically.

**Alternatives considered**: Renumbering every existing level's `path` to
keep `"0"` always meaning "finest" — rejected as unnecessary I/O and risk
(every rename touches an existing, previously-working array) for a property
(`path` values reading as sequential) that has no functional significance.

## Decision: In-place safety = backup root attrs + write new arrays first + validate before committing metadata; `--output` = copy directory first, then extend the copy

**Decision**: For in-place mode: new level arrays are written into the
dataset's existing group first (harmless — nothing existing references them
yet); the dataset's current root attrs are backed up
(`core/backup.py::backup_attrs`, already used by `fix_metadata`/`migrate`);
the new `multiscales[0].datasets` list (existing entries plus the new ones,
correctly ordered) is written; the result is validated
(`io/ome_metadata.py::validate`); on any failure at any point, the newly
written arrays are removed and, if attrs were already updated, they're
restored from the backup (`restore_attrs`, already used by `fix_metadata`) —
existing levels are never touched, so there's nothing to "swap back," unlike
`migrate`'s full-dataset rewrite. For `--output`: the whole dataset directory
is copied to the output path first (`shutil.copytree`, rejecting an
already-existing output path first via a shared `validate_output_path()` —
moved from `migrate.py` into `core/zarr_path.py` so both new commands and
`migrate` share one definition instead of duplicating it), then the exact
same add-levels procedure runs against the copy — the original is never
opened for writing at all in this mode, so "untouched" is trivially true
throughout, not just on success.

**Rationale**: `downsample`/`upsample` only ever *add* data — there's no
existing content that needs a temp-then-swap dance the way `migrate`'s
full-format conversion does. Writing new arrays first (before touching
metadata) means a failure during array-writing leaves the dataset in exactly
its original state (the new arrays are orphaned but harmless, and are
cleaned up); a failure during/after the metadata write is the only case
needing `restore_attrs`. This is cheaper and simpler than `migrate`'s
approach while still satisfying the same "leave the original completely
untouched on failure" requirement (spec FR-005/SC-003).

**Alternatives considered**: Reusing `migrate`'s exact temp-then-swap
pattern (build the *entire* extended dataset in a temp directory, then swap)
— rejected: correct but wasteful, since it would mean copying/rewriting
every existing level's data even though nothing about them changed, for
every in-place `downsample`/`upsample` call — directly against this
feature's own point (only pay for what's *new*).

## Decision: Both commands use the existing generic `CommandFormScreen` in the TUI — no specialized screen needed

**Decision**: Neither command needs a specialized TUI screen. Both take only
simple scalar options (`ZARR_PATH`, an optional `--output` path, an optional
`--num_levels` int, and — `upsample` only — an optional `--smooth` float) —
exactly the shape `CommandFormScreen` already handles generically for
`extract`/`apply_mask`. Both execute directly on Run (no confirm/diff step)
and land on the existing generic `GenericResultScreen`, matching every
command that isn't `fix_metadata`/`migrate`/`inspect`/`config` (spec 004 US7).

**Rationale**: Spec 004's own precedent is that only commands needing
*extra, command-specific* UI (a confirm-before-you-commit step, a rich
report view, etc.) get a specialized screen — `downsample`/`upsample` have
no such need, so adding one would be exactly the kind of speculative
UI/indirection the constitution's Principle I says not to introduce.

**Alternatives considered**: A shared Confirm screen (mirroring
`fix_metadata`/`migrate`'s spec 004 US8 pattern), previewing the levels that
would be added before committing — rejected as out of scope: the user's
request didn't ask for a preview step for these two commands, and per this
session's own established precedent (spec 004 US8's own Assumptions:
"ask before extending this to other commands"), adding a Confirm screen to
commands that weren't asked for one is exactly the kind of unrequested scope
expansion to avoid.
