import React from 'react';
import ExpandableText from './ExpandableText.jsx'; // Import our new component

// --- Styles ---
const cardStyle = {
  border: '1px solid #555',
  borderRadius: '8px',
  padding: '1rem',
  marginBottom: '1rem',
  textAlign: 'left',
  background: '#2a2a2a'
};

const headingStyle = {
  marginTop: 0,
  borderBottom: '1px solid #555',
  paddingBottom: '0.5rem'
};

const detailRowStyle = {
  display: 'flex',
  margin: '0.5rem 0',
  lineHeight: '1.4'
};

const labelStyle = {
  flexBasis: '130px',
  minWidth: '130px',
  fontWeight: 'bold',
  color: '#aaa'
};

// --- Helper Functions ---
const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  } catch (e) {
    return dateString;
  }
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


function ResultDisplay({ result }) {
  if (!result) {
    return null;
  }

  if (result.error) {
    return (
      <div style={cardStyle}>
        <h3 style={{...headingStyle, color: '#ff8a8a' }}>Error</h3>
        <p>{result.error}</p>
      </div>
    );
  }

  return (
    <div>
      {result.channel && (
        <div style={cardStyle}>
          <h3 style={headingStyle}>Channel Details</h3>
          <div style={detailRowStyle}><span style={labelStyle}>Name:</span><span>{result.channel.name}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Subscribers:</span><span>{result.channel.subscriber_count?.toLocaleString()}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Total Videos:</span><span>{result.channel.video_count}</span></div>
          {result.channel.content_breakdown && (
             <div style={detailRowStyle}><span style={labelStyle}>Content:</span><span>{Object.entries(JSON.parse(result.channel.content_breakdown)).map(([type, count]) => `${type}: ${count}`).join(', ')}</span></div>
          )}
          <div style={detailRowStyle}>
            <span style={labelStyle}>Description:</span>
            <ExpandableText text={result.channel.description} maxLength={200} />
          </div>
        </div>
      )}

      {result.video && (
        <div style={cardStyle}>
          <h3 style={headingStyle}>Video Details</h3>
          <div style={detailRowStyle}><span style={labelStyle}>Title:</span><span>{result.video.title}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Channel:</span><span>{result.video.channel_title}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Published:</span><span>{formatDate(result.video.published_at)}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Duration:</span><span>{formatDuration(result.video.duration)}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Views:</span><span>{result.video.view_count?.toLocaleString()}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Likes:</span><span>{result.video.like_count?.toLocaleString()}</span></div>
          <div style={detailRowStyle}>
            <span style={labelStyle}>Description:</span>
            <ExpandableText text={result.video.description} maxLength={200} />
          </div>
        </div>
      )}

      {result.playlist && (
        <div style={cardStyle}>
          <h3 style={headingStyle}>Playlist Details</h3>
          <div style={detailRowStyle}><span style={labelStyle}>Title:</span><span>{result.playlist.title}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Channel:</span><span>{result.playlist.channel_title}</span></div>
          <div style={detailRowStyle}><span style={labelStyle}>Video Count:</span><span>{result.playlist.video_count}</span></div>
          <div style={detailRowStyle}>
            <span style={labelStyle}>Description:</span>
            <ExpandableText text={result.playlist.description} maxLength={200} />
          </div>
        </div>
      )}
    </div>
  );
}

export default ResultDisplay;
