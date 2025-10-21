import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col, Button, ListGroup } from 'react-bootstrap';

// Helper to create the proxy URL
const getProxyUrl = (url) => {
  if (!url) return '';
  return `http://127.0.0.1:8000/api/image-proxy?url=${encodeURIComponent(url)}`;
};

// --- Detail View for a Single Channel ---
function ChannelDetailView({ channelId, onBack }) {
  const [details, setDetails] = useState(null);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`http://127.0.0.1:8000/api/channels/${channelId}`),
      fetch(`http://127.0.0.1:8000/api/channels/${channelId}/videos`)
    ])
    .then(async ([resDetails, resVideos]) => {
      if (!resDetails.ok) throw new Error(`Failed to fetch channel details.`);
      if (!resVideos.ok) throw new Error(`Failed to fetch channel videos.`);
      
      const detailsData = await resDetails.json();
      const videosData = await resVideos.json();

      setDetails(detailsData);
      setVideos(videosData);
    })
    .catch(err => setError(err.message))
    .finally(() => setLoading(false));
  }, [channelId]);

  if (loading) {
    return <div className="text-center"><Spinner animation="border" /></div>;
  }

  if (error) {
    return <Alert variant="danger">{error}</Alert>;
  }

  if (!details) {
    return <Alert variant="warning">Channel data could not be loaded.</Alert>;
  }

  const formatVideoDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch (e) {
      return dateString; // Fallback to original string if parsing fails
    }
  };

  return (
    <Card className="channel-detail-card">
      <Card.Body>
        <Button variant="outline-secondary" onClick={onBack} className="back-button mb-4">
          &larr; Back to Channel List
        </Button>

        {details.banner_url && (
          <img 
            src={getProxyUrl(details.banner_url)} 
            alt={`${details.name} banner`} 
            style={{ width: '100%', height: '200px', objectFit: 'cover', borderRadius: '8px', marginBottom: '1.5rem' }} 
          />
        )}

        <Row>
          <Col md={8}>
            <Card.Title as="h2" className="mb-3">{details.name}</Card.Title>
            <p>
              <strong>Link:</strong>{' '}
              <a href={`https://www.youtube.com/channel/${details.id}`} target="_blank" rel="noopener noreferrer">
                {`https://www.youtube.com/channel/${details.id}`}
              </a>
            </p>
            <p><strong>Subscribers:</strong> {details.subscriber_count?.toLocaleString() || 'N/A'}</p>
            <p><strong>Total Videos:</strong> {details.video_count || 'N/A'}</p>
            {details.description && <p className="mt-3">{details.description}</p>}
          </Col>
          <Col md={4} className="d-flex align-items-center justify-content-center">
            {details.thumbnail_url && 
              <Card.Img src={getProxyUrl(details.thumbnail_url)} className="result-thumbnail" />
            }
          </Col>
        </Row>

        <hr className="my-4" />

        <h4 className="mb-3">Videos in Library</h4>
        {videos.length > 0 ? (
          <div>
            {/* Header Row */}
            <Row className="border-bottom pb-2 mb-2 text-muted fw-bold">
              <Col>Title</Col>
              <Col md="auto">Published at</Col>
              <Col md="auto" className="text-center">Downloaded</Col>
            </Row>

            {/* Video Rows */}
            {videos.map(video => (
              <Row key={video.id} className="py-2 border-bottom align-items-center">
                <Col>{video.title}</Col>
                <Col md="auto">{formatVideoDate(video.published_at)}</Col>
                <Col md="auto" className="text-center" style={{ minWidth: '120px' }}>
                  {video.file_path &&
                    <span title="Downloaded" style={{ fontSize: '1.2rem', color: '#28a745' }}>✓</span>
                  }
                </Col>
              </Row>
            ))}
          </div>
        ) : (
          <p>No videos from this channel have been saved to the library yet.</p>
        )}
      </Card.Body>
    </Card>
  );
}


// --- Main Component for Listing All Channels ---
function ChannelList() {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedChannelId, setSelectedChannelId] = useState(null);

  useEffect(() => {
    if (!selectedChannelId) { // Only fetch list if no channel is selected
      setLoading(true);
      fetch('http://127.0.0.1:8000/api/channels')
        .then(response => {
          if (!response.ok) throw new Error('Failed to fetch channels.');
          return response.json();
        })
        .then(data => {
          const sortedData = data.sort((a, b) => a.name.localeCompare(b.name));
          setChannels(sortedData);
        })
        .catch(err => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [selectedChannelId]); // Re-fetch when we go back to the list

  // --- Render Logic ---
  if (selectedChannelId) {
    return <ChannelDetailView channelId={selectedChannelId} onBack={() => setSelectedChannelId(null)} />;
  }

  let content;
  if (loading) {
    content = <div className="text-center"><Spinner animation="border" role="status"><span className="visually-hidden">Loading...</span></Spinner></div>;
  } else if (error) {
    content = <Alert variant="danger">{error}</Alert>;
  } else if (channels.length === 0) {
    content = <p>No channels have been added to the library yet.</p>;
  } else {
    content = (
      <Row xs={1} sm={2} md={3} lg={4} className="g-4">
        {channels.map(channel => (
          <Col key={channel.id}>
            <Card 
              className="channel-card h-100"
              onClick={() => setSelectedChannelId(channel.id)}
            >
              <Card.Img 
                variant="top" 
                src={getProxyUrl(channel.thumbnail_url) || 'https://via.placeholder.com/150'} 
                className="channel-card-img"
              />
              <Card.Body>
                <Card.Title className="channel-card-title">{channel.name}</Card.Title>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
    );
  }

  return (
    <div>
      <h2 className="mb-4">Channels in Library</h2>
      {content}
    </div>
  );
}

export default ChannelList;