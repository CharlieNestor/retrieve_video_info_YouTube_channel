import React, { useState } from 'react';
import { Form, Button, Container } from 'react-bootstrap';

function Header({ onUrlSubmit }) {
  const [url, setUrl] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    onUrlSubmit(url);
    setUrl('');
  };

  return (
    <header className="app-header">
      <h1 className="app-title">YouTube Library Manager</h1>
      <div className="url-form-container">
        <Form onSubmit={handleSubmit} className="d-flex">
          <Form.Control
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Enter any YouTube Channel, Playlist, or Video URL"
            className="me-2"
            style={{ width: '500px' }} // Increased width
          />
          <Button variant="primary" type="submit">Process URL</Button>
        </Form>
      </div>
    </header>
  );
}

export default Header;
