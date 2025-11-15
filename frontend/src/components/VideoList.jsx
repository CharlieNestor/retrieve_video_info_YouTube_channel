import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col, Badge } from 'react-bootstrap';
import VideoDetailView from './VideoDetailView';
import { getProxyUrl, formatDuration, formatDate } from '../utils';

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
