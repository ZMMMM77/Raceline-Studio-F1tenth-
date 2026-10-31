# Iterative minimum-curvature planning

Minimum-curvature planning defaults to an iterative Gauss-Newton QP solved by OSQP. The original SLSQP solver remains selectable under Advanced calculation settings; shortest-path planning is unchanged. The API accepts `solver: "iterative_qp"` (default for `min_curvature`) or `solver: "legacy"`.

The objective remains the arc-length-weighted squared curvature integral. Each local subproblem linearizes curvature, heading-dependent body clearance and forward progress, with a positive-semidefinite curvature approximation, a bounded step and nonlinear line search. Infeasible starts use an elastic feasibility-restoration QP. Accepted steps periodically update reference points and normals. Original raster obstacles and original CSV boundaries remain fixed across reference updates.

Multiple starts include the supplied reference, an extracted map centerline when unambiguous, and a smoothed reference. Runtime is shared between starts. The selected route has the lowest densely evaluated curvature energy among validated candidates; no claim of global optimality is made. A time limit, plateau or unresolved QP can return the best validated candidate but never a trial point that failed validation.

## Vehicle footprint

The rear axle remains the tracking reference. Vehicle width, length, rear overhang, steering limit, wheelbase and the user safety margin retain their physical values. The full rectangular body is conservatively covered by a row of rotating discs. Each disc covers a longitudinal slice, with radius `sqrt((width/2)^2 + (slice_length/2)^2)`. This covers the interior and corners, rather than checking only four corners. Every disc is checked against the original signed distance field and/or frozen CSV corridor. Unknown map pixels remain blocked.

Final validation checks the spline at dense poses, including the closing seam, and deducts an allowance for between-pose translation/rotation. As with the old planner, these numerical checks are not an analytic continuous-interval certificate. The final curvature, forward progress and self-intersection checks remain mandatory. Map-free CSV planning assumes that the supplied widths describe the real track.

For the new footprint, `min_clearance` is the conservative covered-body-to-boundary clearance and `required_clearance` is the user safety margin. For the old solver these fields describe reference-point distance and enclosing-circle radius plus margin. Compare the physical dimensions and validation model as well as the numeric clearance. Reports include `footprint_model`, `solver`, per-start results and `initial_feasible_curvature_energy`. The output formats and speed model are unchanged.

## Reproduction and comparison

Install dependencies from `requirements.txt`, restart Studio and refresh the page. Choose Minimum curvature; the advanced solver selector allows the original solver to be run on the same input. The original solver comparison changes both the numerical solver and the footprint approximation; improvement against that result cannot be attributed to QP alone. Compare against the feasible reference and different starts under the new footprint to isolate changes within the new planner.

The design follows the iterative reference-update principle discussed in Lecture 14 (pages 50, 57-58) and TUM's minimum-curvature planning work. This implementation uses the Studio's arc-length-weighted objective and original raster constraints; it does not reproduce TUM's implementation verbatim and does not perform lap-time optimization or simulation-based verification.
