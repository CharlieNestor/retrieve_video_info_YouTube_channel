import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col, Badge, Button, Table } from 'react-bootstrap';
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

      </Card.Body>
    </Card>
  );
}

export default VideoDetailView;
