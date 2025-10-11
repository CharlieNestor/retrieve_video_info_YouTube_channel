import React from 'react';

// Style for the floating card container
const cardStyle = {
  background: '#2a2a2a',
  borderRadius: '8px',
  padding: '2rem',
  border: '1px solid #444',
};

function VideoList() {
  return (
    <div style={cardStyle}>
      <h2 className="mb-4">Videos in Library</h2>
      <p>Video management is not yet implemented.</p>
    </div>
  );
}

export default VideoList;
