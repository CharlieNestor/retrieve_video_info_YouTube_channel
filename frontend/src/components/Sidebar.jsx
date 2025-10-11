import React from 'react';
import { Nav } from 'react-bootstrap';

// Style for the floating card container
const cardStyle = {
  background: '#2a2a2a',
  borderRadius: '8px',
  padding: '1rem',
  border: '1px solid #444',
  height: '100%',
};

function Sidebar({ onShowChannels, onShowPlaylists, onShowVideos }) {
  return (
    <div style={cardStyle}>
      <Nav className="flex-column">
        <Nav.Item className="w-100 mb-2">
          <Nav.Link as="button" onClick={onShowChannels} className="btn btn-primary w-100">
            Channels
          </Nav.Link>
        </Nav.Item>
        <Nav.Item className="w-100 mb-2">
          <Nav.Link as="button" onClick={onShowPlaylists} className="btn btn-primary w-100">
            Playlists
          </Nav.Link>
        </Nav.Item>
        <Nav.Item className="w-100">
          <Nav.Link as="button" onClick={onShowVideos} className="btn btn-primary w-100">
            Videos
          </Nav.Link>
        </Nav.Item>
      </Nav>
    </div>
  );
}

export default Sidebar;
