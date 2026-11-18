import { useParams } from 'react-router'
import MeetingDetails from '../components/MeetingDetails'

// The page at /meetings/:id. useParams reads the :id part of the address;
// it is text, e.g. "5". An id that is not a number gets an error message
// from the backend, like a meeting that does not exist.
function MeetingPage() {
  const { id } = useParams()

  // key: when the address changes to another interview, React makes a new
  // MeetingDetails instead of reusing the old one with its old state
  return <MeetingDetails key={id} meetingId={id} />
}

export default MeetingPage
