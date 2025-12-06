import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col, Badge, Button, Table, Form, Modal } from 'react-bootstrap';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import ExpandableText from '../ExpandableText';
import { getProxyUrl, formatDuration, formatDate } from '../utils';

// --- Internal Helper Components ---

const formatTime = (seconds) => {
  if (seconds === null || seconds === undefined) return 'N/A';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  const mStr = m.toString().padStart(2, '0');
  const sStr = s.toString().padStart(2, '0');
  return h > 0 ? `${h}:${mStr}:${sStr}` : `${mStr}:${sStr}`;
};

const ExpandableCell = ({ text }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const textStyle = {
    whiteSpace: isExpanded ? 'normal' : 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    minWidth: 0,
  };

  const containerStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  };

  return (
    <td>
      <div style={isExpanded ? {} : containerStyle}>
        <div style={textStyle}>{text}</div>
        <Button variant="link" size="sm" onClick={toggleExpanded} style={{ padding: '0', lineHeight: '1', marginLeft: '8px', flexShrink: 0 }}>
          {isExpanded ? 'Less' : 'More'}
        </Button>
      </div>
    </td>
  );
};

// --- Main Detail View Component ---

function VideoDetailView({ videoId, onBack }) {
  const [details, setDetails] = useState(null);
  const [transcriptPlainText, setTranscriptPlainText] = useState(null);
  const [transcriptChapters, setTranscriptChapters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transcriptLoading, setTranscriptLoading] = useState(true);
  const [error, setError] = useState(null);
  const [transcriptError, setTranscriptError] = useState(null);
  const [copyButtonText, setCopyButtonText] = useState('Copy Path');
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateStatus, setUpdateStatus] = useState({ message: '', type: '' });

  // State for Delete Feature
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // State for LLM Query Feature
  const [query, setQuery] = useState('');
  const [conversation, setConversation] = useState([]);
  const [isLlmLoading, setIsLlmLoading] = useState(false);
  const [llmError, setLlmError] = useState('');
  const [sessionId, setSessionId] = useState(null);


  const handleCopy = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopyButtonText('Copied!');
      setTimeout(() => setCopyButtonText('Copy Path'), 2000);
    }, (err) => {
      console.error('Failed to copy: ', err);
    });
  };

  const fetchVideoDetails = () => {
    setLoading(true);
    setError(null);
    fetch(`http://127.0.0.1:8000/api/videos/${videoId}`)
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => { throw new Error(err.detail || 'Failed to fetch video details.'); });
        }
        return response.json();
      })
      .then(data => setDetails(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  };

  const fetchTranscript = () => {
    setTranscriptLoading(true);
    setTranscriptError(null);
    setTranscriptPlainText(null);
    setTranscriptChapters([]);
    fetch(`http://127.0.0.1:8000/api/videos/${videoId}/transcript`)
      .then(response => {
        if (!response.ok) {
          if (response.status === 404) return null;
          return response.json().then(err => { throw new Error(err.detail || 'Failed to fetch transcript.'); });
        }
        return response.json();
      })
      .then(data => {
        if (data) {
          setTranscriptPlainText(data.plain_text);
          setTranscriptChapters(data.chapters || []);
        }
      })
      .catch(err => setTranscriptError(err.message))
      .finally(() => setTranscriptLoading(false));
  };

  useEffect(() => {
    fetchVideoDetails();
    fetchTranscript();

    // Session Management Logic
    const storageKey = `chat_session_${videoId}`;
    const storedSession = sessionStorage.getItem(storageKey);

    if (storedSession) {
      // Restore existing session
      setSessionId(storedSession);
      // Note: We currently don't persist the message history in sessionStorage,
      // so the UI will look empty, but the Backend will remember the context.
      // Ideally, we would fetch the history from the backend here, but for now
      // we just ensure the LLM context is preserved.
      setConversation([]);
    } else {
      // Create new session
      const newSessionId = crypto.randomUUID();
      sessionStorage.setItem(storageKey, newSessionId);
      setSessionId(newSessionId);
      setConversation([]);
    }

    setLlmError('');
    setQuery('');
  }, [videoId]);

  const handleUpdate = () => {
    setIsUpdating(true);
    setUpdateStatus({ message: '', type: '' });

    fetch(`http://127.0.0.1:8000/api/videos/${videoId}/update`, {
      method: 'POST',
    })
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => { throw new Error(err.detail || 'Update failed'); });
        }
        return response.json();
      })
      .then(data => {
        setUpdateStatus({ message: data.message || 'Video updated successfully!', type: 'success' });
        fetchVideoDetails();
        fetchTranscript();
      })
      .catch(error => {
        setUpdateStatus({ message: error.message, type: 'danger' });
      })
      .finally(() => {
        setIsUpdating(false);
        setTimeout(() => setUpdateStatus({ message: '', type: '' }), 5000);
      });
  };

  const handleQuerySubmit = (e) => {
    e.preventDefault();
    if (!query.trim() || !sessionId) return;

    setIsLlmLoading(true);
    setLlmError('');
    const currentQuery = query;

    fetch(`http://127.0.0.1:8000/api/videos/${videoId}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: currentQuery,
        session_id: sessionId,
        // lang: 'en' // Optionally specify language
      }),
    })
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => { throw new Error(err.detail || 'Failed to get answer.'); });
        }
        return response.json();
      })
      .then(data => {
        if (data.error) {
          throw new Error(data.error);
        }
        // Add the new question and answer to the conversation history
        setConversation(prev => [...prev, { query: currentQuery, answer: data.answer }]);
        setQuery(''); // Clear the input field
      })
      .catch(error => {
        setLlmError(error.message);
      })
      .finally(() => {
        setIsLlmLoading(false);
      });
  };

  const handleDelete = () => {
    setIsDeleting(true);

    fetch(`http://127.0.0.1:8000/api/videos/${videoId}`, {
      method: 'DELETE',
    })
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => { throw new Error(err.detail || 'Delete failed'); });
        }
        return response.json();
      })
      .then(() => {
        // Success - go back to previous view
        onBack();
      })
      .catch(error => {
        setUpdateStatus({ message: error.message, type: 'danger' });
        setShowDeleteModal(false);
        setIsDeleting(false);
        setTimeout(() => setUpdateStatus({ message: '', type: '' }), 5000);
      });
  };



  if (loading) {
    return <div className="text-center"><Spinner animation="border" /></div>;
  }

  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }

  if (!details) {
    return <Alert variant="warning">Video data could not be loaded.</Alert>;
  }

  return (
    <Card className="channel-detail-card">
      <Card.Body className="pb-5">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <Button variant="outline-secondary" onClick={onBack}>
            &larr; Back
          </Button>
          <Button variant="primary" onClick={handleUpdate} disabled={isUpdating}>
            {isUpdating ? (
              <><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> Updating...</>
            ) : (
              'Update'
            )}
          </Button>
        </div>

        {updateStatus.message && (
          <Alert variant={updateStatus.type} className="mb-4">
            {updateStatus.message}
          </Alert>
        )}

        <Card.Title as="h2" className="mb-1">{details.title}</Card.Title>
        <Card.Subtitle className="mb-3 text-muted">By {details.channel_title}</Card.Subtitle>

        {details.thumbnail_url && (
          <img
            src={getProxyUrl(details.thumbnail_url)}
            alt={`Thumbnail for ${details.title}`}
            style={{ width: '100%', borderRadius: '8px', marginBottom: '1.5rem' }}
          />
        )}

        <div className="d-flex justify-content-between align-items-center mb-2">
          <p className="mb-0">
            <strong>Link:</strong>{' '}
            <a href={`https://www.youtube.com/watch?v=${details.id}`} target="_blank" rel="noopener noreferrer">
              {`https://www.youtube.com/watch?v=${details.id}`}
            </a>
          </p>
          <div style={{ marginLeft: 'auto', paddingRight: '40px' }}>
            {details.downloaded ? (
              <Badge bg="success">Downloaded</Badge>
            ) : (
              <Badge bg="secondary">Not Downloaded</Badge>
            )}
          </div>
        </div>

        {details.downloaded === 1 && details.file_path && (
          <div className="mb-3">
            <div className="d-flex justify-content-between align-items-center">
              <p className="mb-1"><strong>File Path:</strong></p>
              <div style={{ paddingRight: '40px' }}>
                <Button style={{ whiteSpace: 'nowrap' }} variant="outline-secondary" size="sm" onClick={() => handleCopy(details.file_path)}>
                  {copyButtonText}
                </Button>
              </div>
            </div>
            <p className="text-muted" style={{ wordBreak: 'break-all' }}>
              {details.file_path}
            </p>
          </div>
        )}

        <Row className="mb-3">
          <Col><strong>Views:</strong> {details.view_count?.toLocaleString() || 'N/A'}</Col>
          <Col><strong>Likes:</strong> {details.like_count?.toLocaleString() || 'N/A'}</Col>
          <Col><strong>Duration:</strong> {formatDuration(details.duration)}</Col>
          <Col><strong>Published:</strong> {formatDate(details.published_at)}</Col>
        </Row>

        {details.tags && details.tags.length > 0 && (
          <div className="mt-3 mb-3">
            <strong>Tags:</strong>{' '}
            {details.tags.map((tag, index) => (
              <Badge key={index} bg="secondary" className="me-1 mb-1">
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {details.description && (
          <div className="mt-3 mb-5">
            <strong>Description:</strong>
            <ExpandableText text={details.description} maxLength={250} />
          </div>
        )}

        {/* --- AI Query Section --- */}
        <Card className="my-4" bg="dark" border="secondary">
          <Card.Body>
            <Card.Title>Ask the Transcript</Card.Title>

            <div
              className="mb-4 p-3"
              style={{
                maxHeight: '400px',
                overflowY: 'auto',
                backgroundColor: '#1c1c1c',
                borderRadius: '8px'
              }}
            >
              {conversation.length === 0 && !isLlmLoading && (
                <div className="text-center text-muted">
                  Your conversation will appear here.
                </div>
              )}

              {conversation.map((exchange, index) => (
                <div key={index} className="mb-3">
                  {/* User's Question */}
                  <div className="mb-2">
                    <div className="fw-bold small text-muted">You</div>
                    <Card bg="secondary" text="white" className="mb-2">
                      <Card.Body className="p-2">
                        <Card.Text>{exchange.query}</Card.Text>
                      </Card.Body>
                    </Card>
                  </div>

                  {/* Assistant's Answer */}
                  <div>
                    <div className="fw-bold small text-muted">Assistant</div>
                    <Card bg="dark" text="white" style={{ borderColor: '#444' }}>
                      <Card.Body className="p-2">
                        <div className="markdown-content">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {exchange.answer}
                          </ReactMarkdown>
                        </div>
                      </Card.Body>
                    </Card>
                  </div>
                </div>
              ))}

              {isLlmLoading && (
                <div className="text-center mt-3">
                  <Spinner animation="border" size="sm" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </Spinner>
                </div>
              )}
            </div>

            {llmError && <Alert variant="danger">{llmError}</Alert>}

            <Form onSubmit={handleQuerySubmit}>
              <Form.Group className="mb-3">
                <Form.Control
                  as="textarea"
                  rows={2}
                  placeholder="Ask a question about this video's transcript..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  disabled={!transcriptPlainText || isLlmLoading}
                />
                {!transcriptPlainText && <Form.Text className="text-muted">Transcript must be loaded to ask a question.</Form.Text>}
              </Form.Group>
              <Button variant="primary" type="submit" disabled={isLlmLoading || !query.trim()}>
                {isLlmLoading ? (
                  <><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> Asking...</>
                ) : (
                  'Ask'
                )}
              </Button>
            </Form>
          </Card.Body>
        </Card>

        {transcriptChapters && transcriptChapters.length > 0 && (
          <div className="mt-3 mb-5">
            <strong>Chapters:</strong>
            <Table striped bordered hover size="sm" className="mt-2" style={{ tableLayout: 'fixed' }}>
              <thead>
                <tr>
                  <th style={{ width: '12%' }}>Start Time</th>
                  <th style={{ width: '38%' }}>Title</th>
                  <th style={{ width: '50%' }}>Text</th>
                </tr>
              </thead>
              <tbody>
                {transcriptChapters.map((ts, index) => (
                  <tr key={index}>
                    <td>{formatTime(ts.start_time)}</td>
                    <td>{ts.chapter_title}</td>
                    <ExpandableCell text={ts.text} />
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}

        {transcriptLoading ? (
          <div className="text-center mt-3 mb-5"><Spinner animation="border" size="sm" /> Loading transcript...</div>
        ) : transcriptError ? (
          <Alert variant="danger" className="mt-3 mb-5">Error loading transcript: {transcriptError}</Alert>
        ) : transcriptPlainText && (
          <div className="mt-3 mb-5">
            <strong>Full Plain Transcript:</strong><br />
            <ExpandableText text={transcriptPlainText} maxLength={500} />
          </div>
        )}

        {/* Delete Button - Bottom Left */}
        <div className="mt-4">
          <Button
            variant="danger"
            onClick={() => setShowDeleteModal(true)}
            disabled={isDeleting}
          >
            Delete Video
          </Button>
        </div>

      </Card.Body>

      {/* Delete Confirmation Modal */}
      <Modal show={showDeleteModal} onHide={() => setShowDeleteModal(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>Confirm Deletion</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>Are you sure you want to delete this video?</p>
          <p className="text-muted mb-0">
            <strong>{details?.title}</strong>
          </p>
          <p className="text-danger mt-3 mb-0">
            <small>This action cannot be undone.</small>
          </p>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShowDeleteModal(false)} disabled={isDeleting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDelete} disabled={isDeleting}>
            {isDeleting ? (
              <><Spinner as="span" animation="border" size="sm" role="status" aria-hidden="true" /> Deleting...</>
            ) : (
              'Delete'
            )}
          </Button>
        </Modal.Footer>
      </Modal>
    </Card>
  );
}

export default VideoDetailView;
