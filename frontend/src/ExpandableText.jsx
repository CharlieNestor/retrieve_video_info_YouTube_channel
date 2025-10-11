import React, { useState } from 'react';

const buttonStyle = {
  background: 'none',
  border: 'none',
  color: '#0d6efd',
  cursor: 'pointer',
  padding: '0',
  marginLeft: '8px',
  fontWeight: 'bold'
};

function ExpandableText({ text, maxLength = 200 }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!text) {
    return <span>N/A</span>;
  }

  if (text.length <= maxLength) {
    return <span>{text}</span>;
  }

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <span>
      {isExpanded ? text : `${text.substring(0, maxLength)}...`}
      <button onClick={toggleExpanded} style={buttonStyle}>
        {isExpanded ? 'View Less' : 'View More'}
      </button>
    </span>
  );
}

export default ExpandableText;
