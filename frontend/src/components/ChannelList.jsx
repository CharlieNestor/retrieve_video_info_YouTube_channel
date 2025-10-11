import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col } from 'react-bootstrap';

function ChannelList() {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch('http://127.0.0.1:8000/api/channels')
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch channels.');
        }
        return response.json();
      })
      .then(data => {
        // Sort channels alphabetically by name
        const sortedData = data.sort((a, b) => a.name.localeCompare(b.name));
        setChannels(sortedData);
        setLoading(false);
      })
      .catch(error => {
        console.error("Error fetching channels:", error);
        setError(error.message);
        setLoading(false);
      });
  }, []);

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
            <Card className="channel-card h-100">
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
