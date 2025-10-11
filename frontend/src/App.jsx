import React, { useState } from 'react';
import { Container, Row, Col, Alert } from 'react-bootstrap';

import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ChannelList from './components/ChannelList';
import PlaylistList from './components/PlaylistList';
import VideoList from './components/VideoList';
import ResultDisplay from './ResultDisplay';

import './App.css';

function App() {
  const [lastResult, setLastResult] = useState(null);
  const [error, setError] = useState(null);
  
  // State to control which view is active
  const [showChannels, setShowChannels] = useState(false);
  const [showPlaylists, setShowPlaylists] = useState(false);
  const [showVideos, setShowVideos] = useState(false);

  // --- Handlers --- //

  const handleUrlSubmit = (url) => {
    // Only set the result, don't hide other views
    setLastResult(null); // Clear previous result before fetching new one
    setError(null);

    fetch('http://127.0.0.1:8000/api/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url }),
    })
    .then(response => {
      if (!response.ok) {
        return response.json().then(err => { throw new Error(err.detail || 'Network response was not ok'); });
      }
      return response.json();
    })
    .then(data => {
      setLastResult(data);
    })
    .catch(error => {
      setError(error.message);
    });
  };

  const handleShowChannels = () => {
    // Show channels, hide other lists, but DO NOT touch lastResult
    setShowPlaylists(false);
    setShowVideos(false);
    setShowChannels(true);
  };

  const handleShowPlaylists = () => {
    setShowChannels(false);
    setShowVideos(false);
    setShowPlaylists(true);
  };

  const handleShowVideos = () => {
    setShowChannels(false);
    setShowPlaylists(false);
    setShowVideos(true);
  };

  return (
    <div className="App bg-dark text-white" data-bs-theme="dark">
      <Header onUrlSubmit={handleUrlSubmit} />

      <Container style={{ maxWidth: '1200px' }}>
        
        {error && (
          <Row className="justify-content-md-center">
            <Col md={10} lg={8}>
              <Alert variant="danger" className="mt-4">{error}</Alert>
            </Col>
          </Row>
        )}

        {lastResult && (
          <Row className="justify-content-md-center">
            <Col md={10} lg={8}>
              <div className="mt-3 mb-5">
                <h2 className="mb-3">Last Processed Item</h2>
                <ResultDisplay result={lastResult} />
              </div>
            </Col>
          </Row>
        )}

        <Row>
          <Col md={3} lg={2}>
            <Sidebar 
              onShowChannels={handleShowChannels}
              onShowPlaylists={handleShowPlaylists}
              onShowVideos={handleShowVideos}
            />
          </Col>
          <Col md={9} lg={10}>
            {showChannels && <ChannelList />}
            {showPlaylists && <PlaylistList />}
            {showVideos && <VideoList />}
          </Col>
        </Row>
      </Container>
    </div>
  );
}

export default App;
