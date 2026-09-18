# ManimGL Animation Taxonomy (source of truth)

> Docs site `https://3b1b.github.io/manim/` covers install/quickstart only. Real API lives in `3b1b/manim:manimlib/animation/*.py` (master, enumerated Sep 2026).

## creation.py

`ShowPartial`, `ShowCreation`, `Uncreate`, `DrawBorderThenFill`, `Write`, `ShowIncreasingSubsets`, `ShowSubmobjectsOneByOne`, `AddTextWordByWord`

Use for: text/border entry. `Write(txt)`, `DrawBorderThenFill(rect)`, `ShowCreation(line, lag_ratio=0.01, run_time=2)`.

## fading.py

`Fade`, `FadeIn`, `FadeOut`, `FadeInFromPoint`, `FadeOutToPoint`, `FadeTransform`, `FadeTransformPieces`, `VFadeIn`, `VFadeOut`, `VFadeInThenOut`

Use for: enter/exit + semantic morph (`FadeTransform(entry, sym)` in attention.py collapse).

## growing.py

`GrowFromPoint`, `GrowFromCenter`, `GrowFromEdge`, `GrowArrow`

Use for: arrows, braces (`GrowArrow(arrow)`, `GrowFromCenter(brace)`).

## indication.py

`FocusOn`, `Indicate`, `Flash`, `CircleIndicate`, `ShowPassingFlash`, `FlashAround`, `FlashUnder`, `ShowCreationThenDestruction`, `ApplyWave`, `WiggleOutThenIn`, `TurnInsideOut`, `FlashyFadeIn`

Use for: emphasis without layout change.

## movement.py

`Homotopy`, `PhaseFlow`, `MoveAlongPath`

Use for: path-following (continuous).

## numbers.py

`ChangingDecimal`, `ChangeDecimalToValue`, `CountInFrom`

Use for: `CountInFrom(dim_value, 0)` + `Brace` pattern (attention.py dim 12288).

## transform.py

`Transform`, `ReplacementTransform`, `TransformFromCopy`, `MoveToTarget`, `ApplyMethod`, `Restore`, `ApplyFunction`, `ApplyMatrix`, `CyclicReplace`, `Swap`

Use for: relate/morph. Target idiom:
```python
m.target = m.generate_target()
# mutate target ...
self.play(MoveToTarget(m, lag_ratio=0.1, run_time=2))
m.refresh_bounding_box(recurse_down=True)
```

## composition.py (most important for complex scenes)

`AnimationGroup`, `Succession`, `LaggedStart`, `LaggedStartMap`

Idioms from `attention.py`:
```python
LaggedStartMap(FadeIn, thumbs, shift=UP, lag_ratio=0.5)
LaggedStart((TransformFromCopy(a,b) for a,b in zip(X,Y)), lag_ratio=0.05)
AnimationGroup(FadeTransform(e,s), MoveToTarget(b))
Succession(FadeIn(x), x.animate.shift(UP))
```

## update.py

`UpdateFromFunc`, `UpdateFromAlphaFunc`, `MaintainPositionRelativeTo`

Use for: live tracking / updaters.

## specialized.py

`Broadcast(LaggedStart)`
