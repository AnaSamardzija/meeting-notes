// The sections of a loaded meeting. A section is shown only when the meeting
// has something for it: the transcript arrives before the summary, and it
// stays when the summary could not be generated.
function MeetingContent({ meeting }) {
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

      {meeting.summary && (
        <section className="mt-4">
          <h3 className="h6">Summary</h3>
          <p>{meeting.summary}</p>

          {meeting.key_topics?.length > 0 && (
            <>
              <h4 className="h6">Key topics</h4>
              <ul className="mb-0">
                {/* The index is the key: two topics can have the same text,
                    and the list is never reordered */}
                {meeting.key_topics.map((topic, index) => (
                  <li key={index}>{topic}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {/* Only for a processed meeting: before that an empty list would only
          mean that the items have not been generated yet */}
      {meeting.status === 'done' && (
        <section className="mt-4">
          <h3 className="h6">Action items</h3>
          {meeting.action_items.length === 0 ? (
            <p className="text-secondary mb-0">No action items.</p>
          ) : (
            <ul className="mb-0">
              {meeting.action_items.map((item) => (
                <li key={item.id}>
                  {/* The assignee is missing when the meeting does not say
                      who is responsible */}
                  {item.assignee && <strong>{item.assignee}: </strong>}
                  {item.description}
                </li>
              ))}
            </ul>
          )}
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
