// One section of the insights (likes, dislikes or wants): a heading and its
// items, each with a bold title. Nothing is shown when the section is empty.
// ordered: a numbered list, for the wants, which come the most important first.
function InsightList({ heading, items, ordered = false }) {
  if (!items?.length) {
    return null
  }

  // A tag name in a variable: JSX treats a capitalized name as the element to
  // create, so <List> becomes <ol> or <ul>
  const List = ordered ? 'ol' : 'ul'
  return (
    <section className="mt-3">
      <h4 className="h6">{heading}</h4>
      <List className="mb-0">
        {/* The index is the key: two items can have the same title, and the
            list is never reordered */}
        {items.map((item, index) => (
          <li key={index}>
            <strong>{item.title}:</strong> {item.explanation}
          </li>
        ))}
      </List>
    </section>
  )
}

// The sections of a loaded meeting. A section is shown only when the meeting
// has something for it: the transcript arrives before the insights, and it
// stays when the insights could not be generated.
function MeetingContent({ meeting }) {
  const { interviewee, insights } = meeting
  // The name, the role and the location are each null when the interview
  // does not say them
  const name = interviewee?.name
  const roleAndLocation = [interviewee?.role, interviewee?.location]
    .filter(Boolean)
    .join(' · ')

  return (
    <>
      <dl className="row mb-0">
        <dt className="col-sm-3">File</dt>
        <dd className="col-sm-9">{meeting.original_filename}</dd>
        <dt className="col-sm-3">Uploaded</dt>
        <dd className="col-sm-9">
          {new Date(meeting.uploaded_at).toLocaleString()}
        </dd>
        {meeting.processed_at && (
          <>
            <dt className="col-sm-3">Processed</dt>
            <dd className="col-sm-9">
              {new Date(meeting.processed_at).toLocaleString()}
            </dd>
          </>
        )}
      </dl>

      {insights && (
        <section className="mt-4">
          <h3 className="h5 mb-1">
            {name ? `${name}: key insights` : 'Key insights'}
          </h3>
          {roleAndLocation && (
            <p className="text-secondary mb-0">{roleAndLocation}</p>
          )}

          {insights.takeaway && (
            <section className="mt-3">
              <h4 className="h6">Takeaway</h4>
              <p className="mb-0">{insights.takeaway}</p>
            </section>
          )}
          {insights.context && (
            <section className="mt-3">
              <h4 className="h6">Context</h4>
              <p className="mb-0">{insights.context}</p>
            </section>
          )}
          <InsightList heading="What they like" items={insights.likes} />
          <InsightList heading="What they dislike" items={insights.dislikes} />
          <InsightList heading="What they want" items={insights.wants} ordered />
        </section>
      )}

      {meeting.transcript && (
        <section className="mt-4">
          <h3 className="h6">Transcript</h3>
          <div className="transcript border rounded bg-body-tertiary p-3">
            {meeting.transcript}
          </div>
        </section>
      )}
    </>
  )
}

export default MeetingContent
