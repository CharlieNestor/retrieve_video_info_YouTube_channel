import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col, Badge, Button } from 'react-bootstrap';
import ExpandableText from '../ExpandableText'; // Assuming ExpandableText is in the parent directory

// --- Helper Functions ---

const getProxyUrl = (url) => {
  if (!url) return '';
  return `http://127.0.0.1:8000/api/image-proxy?url=${encodeURIComponent(url)}`;
};

const formatDuration = (seconds) => {
  if (seconds === null || seconds === undefined) return 'N/A';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  const hStr = h > 0 ? `${h}:` : '';
  const mStr = m.toString().padStart(2, '0');
  const sStr = s.toString().padStart(2, '0');
  return `${hStr}${mStr}:${sStr}`;
};

const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch (e) {
    return dateString;
  }
};

// --- Detail View for a Single Video ---

function VideoDetailView({ videoId, onBack }) {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch(`http://127.0.0.1:8000/api/videos/${videoId}`)
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => { throw new Error(err.detail || 'Failed to fetch video details.'); });
        }
        return response.json();
      })
      .then(data => {
        setDetails(data);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [videoId]);

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
    <Card className="channel-detail-card"> {/* Reusing similar styling */}
      <Card.Body>
        <Button variant="outline-secondary" onClick={onBack} className="back-button mb-4">
          &larr; Back to Video List
        </Button>

        <Card.Title as="h2" className="mb-1">{details.title}</Card.Title>
        <Card.Subtitle className="mb-3 text-muted">By {details.channel_title}</Card.Subtitle>

        {details.thumbnail_url && (
            <img 
                src={getProxyUrl(details.thumbnail_url)} 
                alt={`Thumbnail for ${details.title}`} 
                style={{ width: '100%', borderRadius: '8px', marginBottom: '1.5rem' }} 
            />
        )}

        <p>
          <strong>Link:</strong>{' '}
          <a href={`https://www.youtube.com/watch?v=${details.id}`} target="_blank" rel="noopener noreferrer">
            {`https://www.youtube.com/watch?v=${details.id}`}
          </a>
        </p>

        <Row className="mb-3">
            <Col><strong>Views:</strong> {details.view_count?.toLocaleString() || 'N/A'}</Col>
            <Col><strong>Likes:</strong> {details.like_count?.toLocaleString() || 'N/A'}</Col>
            <Col><strong>Duration:</strong> {formatDuration(details.duration)}</Col>
            <Col><strong>Published:</strong> {formatDate(details.published_at)}</Col>
        </Row>

        {details.description && (
            <div className="mt-3">
                <strong>Description:</strong>
                <ExpandableText text={details.description} maxLength={250} />
            </div>
        )}

      </Card.Body>
    </Card>
  );
}


// --- Main Component for Listing All Videos ---

function VideoList() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedVideoId, setSelectedVideoId] = useState(null);

  useEffect(() => {
    // Only fetch the list if no specific video is selected
    if (!selectedVideoId) {
      setLoading(true);
      fetch('http://127.0.0.1:8000/api/videos')
        .then(response => {
          if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || 'Failed to fetch videos.'); });
          }
          return response.json();
        })
        .then(data => {
          setVideos(data);
        })
        .catch(err => {
          setError(err.message);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [selectedVideoId]); // Re-fetch when we return to the list view

  // --- Render Logic ---

  if (selectedVideoId) {
    return <VideoDetailView videoId={selectedVideoId} onBack={() => setSelectedVideoId(null)} />;
  }

  let content;
  if (loading) {
    content = (
      <div className="text-center">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  } else if (error) {
    content = <Alert variant="danger">{error}</Alert>;
  } else if (videos.length === 0) {
    content = <p>No videos have been added to the library yet.</p>;
  } else {
    content = (
      <div className="d-flex flex-column gap-3">
        {videos.map(video => (
          <Card 
            key={video.id} 
            className="video-list-item-card is-clickable"
            onClick={() => setSelectedVideoId(video.id)}
          >
            <Row className="g-0">
              {/* Thumbnail Column */}
              <Col md={4} lg={3} className="d-flex align-items-center">
                <Card.Img src={getProxyUrl(video.thumbnail_url)} className="video-list-thumbnail" />
              </Col>

              {/* Details Column */}
              <Col md={8} lg={9}>
                <Card.Body>
                  <Card.Title className="mb-2">{video.title}</Card.Title>
                  <Card.Subtitle className="mb-2 text-muted">{video.channel_title}</Card.Subtitle>
                  
                  <div className="d-flex justify-content-between align-items-center mt-3">
                    <small className="text-muted">
                      {formatDate(video.published_at)} &bull; {formatDuration(video.duration)}
                    </small>
                    {video.downloaded ? (
                      <Badge bg="success">Downloaded</Badge>
                    ) : (
                      <Badge bg="secondary">Not Downloaded</Badge>
                    )}
                  </div>
                </Card.Body>
              </Col>
            </Row>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div>
      <h2 className="mb-4">All Videos in Library</h2>
      {content}
    </div>
  );
}

export default VideoList;
