// Turns the summary of a meeting into text for the clipboard, so it can be
// pasted into an email or Slack, and writes it to the clipboard.

// The headings of the summary sections. The details page and the copied
// summary both use them, so they always say the same.
export const SUMMARY_HEADINGS = {
  takeaway: 'Takeaway',
  context: 'Context',
  likes: 'What they like',
  dislikes: 'What they dislike',
  wants: 'What they want',
}

// The sections in the order of the page: first the ones that are one text,
// then the lists. The wants are numbered, the most important first.
const TEXT_SECTIONS = ['takeaway', 'context']
const LIST_SECTIONS = [
  { key: 'likes', ordered: false },
  { key: 'dislikes', ordered: false },
  { key: 'wants', ordered: true },
]

// "Name: key insights", or "Key insights" when the interview does not say
// the name
export function summaryHeader(interviewee) {
  const name = interviewee?.name
  return name ? `${name}: key insights` : 'Key insights'
}

// "Role · Location", or only one of them, or '' when neither is known
export function roleAndLocation(interviewee) {
  return [interviewee?.role, interviewee?.location].filter(Boolean).join(' · ')
}

// The summary as plain text: the sections are separated by an empty line,
// the items of a list start with "-" (or the number for the wants), and an
// empty section is left out.
export function summaryToText({ interviewee, insights }) {
  const blocks = [
    [summaryHeader(interviewee), roleAndLocation(interviewee)]
      .filter(Boolean)
      .join('\n'),
  ]

  for (const key of TEXT_SECTIONS) {
    if (insights[key]) {
      blocks.push(`${SUMMARY_HEADINGS[key]}\n${insights[key]}`)
    }
  }
  for (const { key, ordered } of LIST_SECTIONS) {
    const items = insights[key]
    if (items?.length) {
      const lines = items.map((item, index) => {
        const marker = ordered ? `${index + 1}.` : '-'
        return `${marker} ${item.title}: ${item.explanation}`
      })
      blocks.push([SUMMARY_HEADINGS[key], ...lines].join('\n'))
    }
  }

  return blocks.join('\n\n')
}

// The HTML is built as a string, so React does not escape the text here as
// it does in JSX: a "<" in the summary would otherwise become a tag.
function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

// The summary as HTML with bold headings and lists. The headings are bold
// paragraphs and not <h3>: Slack ignores headings, and in an email they are
// too big.
export function summaryToHtml({ interviewee, insights }) {
  const parts = [`<p><strong>${escapeHtml(summaryHeader(interviewee))}</strong></p>`]
  const roleLine = roleAndLocation(interviewee)
  if (roleLine) {
    parts.push(`<p>${escapeHtml(roleLine)}</p>`)
  }

  for (const key of TEXT_SECTIONS) {
    if (insights[key]) {
      parts.push(
        `<p><strong>${escapeHtml(SUMMARY_HEADINGS[key])}</strong><br>` +
          `${escapeHtml(insights[key])}</p>`,
      )
    }
  }
  for (const { key, ordered } of LIST_SECTIONS) {
    const items = insights[key]
    if (items?.length) {
      const tag = ordered ? 'ol' : 'ul'
      const listItems = items
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.title)}:</strong> ` +
            `${escapeHtml(item.explanation)}</li>`,
        )
        .join('')
      parts.push(
        `<p><strong>${escapeHtml(SUMMARY_HEADINGS[key])}</strong></p>` +
          `<${tag}>${listItems}</${tag}>`,
      )
    }
  }

  return parts.join('')
}

// The browser gives the clipboard only to pages on https or localhost; on
// any other page navigator.clipboard does not exist.
function getClipboard() {
  if (!navigator.clipboard) {
    throw new Error('The clipboard is not available on this page')
  }
  return navigator.clipboard
}

// Copies the summary both as HTML and as plain text: the place it is pasted
// into takes the HTML when it can show formatting, and the text otherwise.
// Throws when the browser does not allow it.
export async function copySummary(meeting) {
  const clipboard = getClipboard()
  if (typeof ClipboardItem === 'undefined') {
    throw new Error('This browser cannot copy formatted text')
  }
  const item = new ClipboardItem({
    'text/html': new Blob([summaryToHtml(meeting)], { type: 'text/html' }),
    'text/plain': new Blob([summaryToText(meeting)], { type: 'text/plain' }),
  })
  await clipboard.write([item])
}

// Copies plain text, e.g. the transcript. Throws when the browser does not
// allow it.
export async function copyText(text) {
  await getClipboard().writeText(text)
}
