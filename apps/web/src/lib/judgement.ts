// Honest-labelling map: for rules where axe can only verify the mechanical
// half of a fix, say so next to the remediation. An axe re-scan can confirm
// "an alt attribute now exists"; it cannot confirm the alt text is *right*.
// Keeping this in the UI is the difference between "verified" meaning
// something and it being marketing.

const NOTES: Record<string, string> = {
	'image-alt':
		'axe verifies an alt attribute exists — only a human can judge whether the text actually describes the image.',
	'input-image-alt':
		'axe verifies the image button has a text alternative — whether it describes the action is a human call.',
	'area-alt':
		'axe verifies the area has a text alternative — whether it describes the link target is a human call.',
	'frame-title':
		'axe verifies a title exists — whether it meaningfully identifies the frame content needs human review.',
	'document-title':
		'axe verifies a title exists — whether it describes the page is a human call.',
	'link-name':
		'axe verifies the link has an accessible name — whether the name makes sense out of context ("read more" passes) needs human review.',
	'button-name':
		'axe verifies the button has an accessible name — whether it describes the action is a human call.',
	label:
		'axe verifies the control is labelled — whether the label wording is right for the field needs human review.',
	'color-contrast':
		'axe measures the new contrast ratio mechanically, but a colour change may need design sign-off before shipping.',
	'heading-order':
		'axe verifies heading levels no longer skip — whether the heading structure reflects the actual content hierarchy is a human call.',
	'empty-heading':
		'axe verifies the heading has content — whether it summarises the section below it is a human call.',
	'select-name':
		'axe verifies the select is labelled — whether the label wording is right needs human review.'
};

export function judgementNote(ruleId: string): string | null {
	return NOTES[ruleId] ?? null;
}
