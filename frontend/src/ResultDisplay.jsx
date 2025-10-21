import React, { useState, useEffect } from 'react';
import { Card, Row, Col } from 'react-bootstrap';
import ExpandableText from './ExpandableText.jsx';

// Helper to create the proxy URL
const getProxyUrl = (url) => {
  if (!url) return '';
  return `http://127.0.0.1:8000/api/image-proxy?url=${encodeURIComponent(url)}`;
};

// --- Styles ---
const cardStyle = {
  border: '1px solid #555',
  borderRadius: '8px',
  padding: '1.5rem',
  marginBottom: '1rem',
  textAlign: 'left',
  background: '#2a2a2a'
};

const headingStyle = {
  marginTop: 0,
  borderBottom: '1px solid #555',
  paddingBottom: '0.5rem',
  marginBottom: '1rem'
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

// --- Main Component ---
function ResultDisplay({ result }) {
  const [channelThumbnail, setChannelThumbnail] = useState(null);

  useEffect(() => {
    setChannelThumbnail(null); // Reset on new result
    if (result && result.playlist && result.playlist.channel_id) {
      fetch(`http://127.0.0.1:8000/api/channels/${result.playlist.channel_id}`)
        .then(response => response.json())
        .then(data => {
          if (data && data.thumbnail_url) {
            setChannelThumbnail(data.thumbnail_url);
          }
        })
        .catch(error => console.error("Failed to fetch channel thumbnail for playlist:", error));
    }
  }, [result]);

  if (!result) return null;

  if (result.error) {
    return (
      <div style={cardStyle}>
        <h3 style={{...headingStyle, color: '#ff8a8a' }}>Error</h3>
        <p>{result.error}</p>
      </div>
    );
  }

  const item = result.channel || result.video || result.playlist;
  if (!item) return null;

  const itemType = result.channel ? 'channel' : (result.video ? 'video' : 'playlist');
  const thumbnailUrl = itemType === 'playlist' ? channelThumbnail : item.thumbnail_url;

  const renderMetadata = () => {
    switch (itemType) {
      case 'channel':
        return (
          <>
            <div style={detailRowStyle}><span style={labelStyle}>Name:</span><span>{item.name}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Subscribers:</span><span>{item.subscriber_count?.toLocaleString()}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Total Videos:</span><span>{item.video_count}</span></div>
            {item.content_breakdown && (
              <div style={detailRowStyle}><span style={labelStyle}>Content:</span><span>{Object.entries(JSON.parse(item.content_breakdown)).map(([type, count]) => `${type}: ${count}`).join(', ')}</span></div>
            )}
          </>
        );
      case 'video':
        return (
          <>
            <div style={detailRowStyle}><span style={labelStyle}>Title:</span><span>{item.title}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Channel:</span><span>{item.channel_title}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Published:</span><span>{formatDate(item.published_at)}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Duration:</span><span>{formatDuration(item.duration)}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Views:</span><span>{item.view_count?.toLocaleString()}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Likes:</span><span>{item.like_count?.toLocaleString()}</span></div>
          </>
        );
      case 'playlist':
        return (
          <>
            <div style={detailRowStyle}><span style={labelStyle}>Title:</span><span>{item.title}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Channel:</span><span>{item.channel_title}</span></div>
            <div style={detailRowStyle}><span style={labelStyle}>Video Count:</span><span>{item.video_count}</span></div>
          </>
        );
      default: return null;
    }
  };

  return (
    <div style={cardStyle}>
      <h3 style={headingStyle}>{`${itemType.charAt(0).toUpperCase() + itemType.slice(1)} Details`}</h3>
      
      <Row>
        {/* Left Column: Metadata */}
        <Col md={thumbnailUrl ? 8 : 12}>
          {renderMetadata()}
        </Col>

        {/* Right Column: Thumbnail */}
        {thumbnailUrl && (
          <Col md={4} className="d-flex align-items-center justify-content-center">
            <Card.Img src={getProxyUrl(thumbnailUrl)} className="result-thumbnail" />
          </Col>
        )}
      </Row>

      {/* Bottom Section: Description */}
      {item.description && (
        <div style={{...detailRowStyle, marginTop: '1rem'}}>
          <span style={labelStyle}>Description:</span>
          <ExpandableText text={item.description} maxLength={200} />
        </div>
      )}
    </div>
  );
}

export default ResultDisplay;