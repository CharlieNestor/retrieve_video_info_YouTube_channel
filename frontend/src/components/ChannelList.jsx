import React, { useState, useEffect } from 'react';
import { Table, Spinner, Alert } from 'react-bootstrap';

// Style for the floating card container
const cardStyle = {
  background: '#2a2a2a',
  borderRadius: '8px',
  padding: '2rem',
  border: '1px solid #444',
};

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
        setChannels(data);
        setLoading(false);
      })
      .catch(error => {
        console.error("Error fetching channels:", error);
        setError(error.message);
        setLoading(false);
      });
  }, []);

  let cardContent;
  if (loading) {
    cardContent = <Spinner animation="border" role="status"><span className="visually-hidden">Loading...</span></Spinner>;
  } else if (error) {
    cardContent = <Alert variant="danger">{error}</Alert>;
  } else if (channels.length === 0) {
    cardContent = <p>No channels have been added to the library yet.</p>;
  } else {
    cardContent = (
      <Table hover responsive variant="dark">
        <thead>
          <tr>
            <th>#</th>
            <th>Channel Name</th>
            <th>Subscribers</th>
            <th>Videos</th>
          </tr>
        </thead>
        <tbody>
          {channels.map((channel, index) => (
            <tr key={channel.id}>
              <td>{index + 1}</td>
              <td>{channel.name}</td>
              <td>{channel.subs}</td>
              <td>{channel.videos}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    );
  }

  return (
    <div style={cardStyle}>
      <h2 className="mb-4">Channels in Library</h2>
      {cardContent}
    </div>
  );
}

export default ChannelList;
