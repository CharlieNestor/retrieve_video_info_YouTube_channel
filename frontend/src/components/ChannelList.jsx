import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col, Button, ListGroup } from 'react-bootstrap';

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

  return (
    <Card className="channel-detail-card">
      <Card.Body>
        <Button variant="outline-secondary" onClick={onBack} className="back-button mb-4">
          &larr; Back to Channel List
        </Button>

        <Row>
          <Col md={8}>
            <Card.Title as="h2" className="mb-3">{details.name}</Card.Title>
            <p><strong>Subscribers:</strong> {details.subscriber_count?.toLocaleString() || 'N/A'}</p>
            <p><strong>Total Videos:</strong> {details.video_count || 'N/A'}</p>
            {details.description && <p className="mt-3">{details.description}</p>}
          </Col>
          <Col md={4} className="d-flex align-items-center justify-content-center">
            {details.thumbnail_url && 
              <Card.Img src={details.thumbnail_url} className="result-thumbnail" />
            }
          </Col>
        </Row>

        <hr className="my-4" />

        <h4 className="mb-3">Videos in Library</h4>
        {videos.length > 0 ? (
          <ListGroup variant="flush">
            {videos.map(video => (
              <ListGroup.Item key={video.id} className="bg-transparent text-white">
                {video.title}
              </ListGroup.Item>
            ))}
          </ListGroup>
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
                src={channel.thumbnail_url || 'https://via.placeholder.com/150'} 
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
