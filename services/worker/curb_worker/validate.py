"""The `validate` tool's mechanics.

This is the deterministic half of the agent's self-check. The agent
proposes a patch; we apply it in the live Playwright page, re-run axe
scoped to the parent of the original node, and report whether the target
violation is gone and whether anything new appeared.

Kept separate from the Pydantic AI Agent definition so the patch / axe
plumbing can be tested without an LLM.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from curb_shared import Patch, ValidationResult, Violation
from playwright.async_api import Page

from curb_worker.detector import _AXE_BUNDLE, _AXE_OPTIONS, _parse_axe_results


async def _scoped_axe(page: Page, scope_selector: str) -> list[Violation]:
    """Run axe-core scoped to a single CSS selector. Returns Curb Violation rows
    (with a throwaway audit_id) so callers can compare rule_ids."""
    await page.add_script_tag(content=_AXE_BUNDLE)
    raw: dict[str, Any] = await page.evaluate(
        """async ({selector, opts}) => {
            const el = document.querySelector(selector);
            if (!el) return { violations: [] };
            return await axe.run(el, opts);
        }""",
        {"selector": scope_selector, "opts": _AXE_OPTIONS},
    )
    return _parse_axe_results(uuid4(), raw)


async def _parent_selector(page: Page, target_selector: str) -> str:
    """Find a stable selector for the parent of the target node.

    We use the parent (not the target) as the axe scope because the patch
    may replace the target element entirely, breaking the original selector.
    """
    sel: str = await page.evaluate(
        """(target) => {
            const el = document.querySelector(target);
            if (!el) return 'body';
            const p = el.parentElement;
            if (!p || p === document.body) return 'body';
            // Build a deterministic selector for the parent.
            if (p.id) return '#' + CSS.escape(p.id);
            const tag = p.tagName.toLowerCase();
            const cls = Array.from(p.classList).map(c => '.' + CSS.escape(c)).join('');
            return tag + cls;
        }""",
        target_selector,
    )
    return sel


async def apply_patch_and_check(
    page: Page,
    *,
    target_selector: str,
    fixed_markup: str,
    original_rule_id: str,
    baseline_rule_ids: frozenset[str],
) -> ValidationResult:
    """Apply the patch in-place, re-run scoped axe, compare to baseline.

    `target_selector` is what axe gave us at detection time. axe selectors
    use ' > ' between segments so they're CSS-valid here.

    `baseline_rule_ids` is the set of rule ids that fired in the scoped
    region before the patch — anything in the new run *not* in this set is
    counted as a regression.
    """
    # Use only the inner-most segment of axe's '>>> '-joined path so the
    # selector evaluates in the current document (no shadow / iframe).
    flat_selector = target_selector.rsplit(" >>> ", maxsplit=1)[-1]
    scope = await _parent_selector(page, flat_selector)

    # Root-level elements (<html>) can't have their outerHTML replaced
    # because their parent is the Document node. For those, mutate attributes
    # in place instead — extract attrs from the proposed markup and apply
    # them. axe-level attribute fixes (html-has-lang, viewport-meta, …) all
    # work this way; element-replacement only matters for body-descendant fixes.
    applied: bool = await page.evaluate(
        """({selector, markup}) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            if (el === document.documentElement) {
                // Root: parse the proposed outerHTML, copy its attributes onto
                // the live element.
                const tmp = new DOMParser().parseFromString(markup, 'text/html');
                const proposed = tmp.documentElement;
                if (!proposed) return false;
                // Clear existing attributes that aren't in the proposed markup,
                // then set every proposed attribute.
                const wantedNames = new Set(
                    Array.from(proposed.attributes).map(a => a.name)
                );
                for (const a of Array.from(el.attributes)) {
                    if (!wantedNames.has(a.name)) el.removeAttribute(a.name);
                }
                for (const a of Array.from(proposed.attributes)) {
                    el.setAttribute(a.name, a.value);
                }
                return true;
            }
            el.outerHTML = markup;
            return true;
        }""",
        {"selector": flat_selector, "markup": fixed_markup},
    )
    if not applied:
        return ValidationResult(
            resolved=False,
            new_violations=[],
            notes=f"target selector {flat_selector!r} did not match any node",
        )

    after = await _scoped_axe(page, scope)
    after_rule_ids = {v.rule_id for v in after}
    resolved = original_rule_id not in after_rule_ids
    new_violations = sorted(after_rule_ids - baseline_rule_ids)
    return ValidationResult(
        resolved=resolved,
        new_violations=new_violations,
        notes="" if resolved else f"{original_rule_id} still flags this region",
    )


async def baseline_for(page: Page, violation: Violation) -> tuple[str, frozenset[str]]:
    """Snapshot the rule ids in the violation's parent region *before* any patch.

    Anything that appears in the after-patch axe run that wasn't in this set
    is a regression introduced by the proposed fix.
    """
    flat_selector = violation.selector.split(" >>> ")[-1]
    scope = await _parent_selector(page, flat_selector)
    before = await _scoped_axe(page, scope)
    return scope, frozenset(v.rule_id for v in before)


# Tiny helper for the Patch model used inside the agent's tool signature.
def patch_for(violation_id: UUID, target_selector: str, original: str, fixed: str) -> Patch:
    return Patch(
        target_selector=target_selector,
        original=original,
        fixed=fixed,
        unified_diff="",  # the agent fills this; not load-bearing for validate.
    )
