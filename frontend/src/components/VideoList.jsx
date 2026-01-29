import React, { useState, useEffect } from 'react';
import { Card, Spinner, Alert, Row, Col, Badge, Pagination } from 'react-bootstrap';
import VideoDetailView from './VideoDetailView';
import { getProxyUrl, formatDuration, formatDate } from '../utils';

// --- Main Component for Listing All Videos ---

function VideoList() {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalVideos, setTotalVideos] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const perPage = 50;

  useEffect(() => {
    // Only fetch the list if no specific video is selected
    if (!selectedVideoId) {
      setLoading(true);
      fetch(`http://127.0.0.1:8000/api/videos?page=${currentPage}&per_page=${perPage}`)
        .then(response => {
          if (!response.ok) {
            return response.json().then(err => { throw new Error(err.detail || 'Failed to fetch videos.'); });
          }
          return response.json();
        })
        .then(data => {
          setVideos(data.videos);
          setTotalVideos(data.total);
          setTotalPages(data.total_pages);
        })
        .catch(err => {
          setError(err.message);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [selectedVideoId, currentPage]); // Re-fetch when page changes or returning to list

  const handlePageChange = (pageNumber) => {
    setCurrentPage(pageNumber);
    window.scrollTo({ top: 0, behavior: 'smooth' }); // Scroll to top on page change
  };

  // Build pagination items
  const renderPaginationItems = () => {
    const items = [];
    const maxVisible = 10; // Maximum number of page buttons to show
    
    // Always show first page
    items.push(
      <Pagination.First key="first" onClick={() => handlePageChange(1)} disabled={currentPage === 1} />
    );
    items.push(
      <Pagination.Prev key="prev" onClick={() => handlePageChange(currentPage - 1)} disabled={currentPage === 1} />
    );

    // Calculate range of pages to show
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    // Adjust start if we're near the end
    if (endPage - startPage < maxVisible - 1) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }

    // Add ellipsis at start if needed
    if (startPage > 1) {
      items.push(<Pagination.Ellipsis key="ellipsis-start" disabled />);
    }

    // Add page numbers
    for (let page = startPage; page <= endPage; page++) {
      items.push(
        <Pagination.Item
          key={page}
          active={page === currentPage}
          onClick={() => handlePageChange(page)}
        >
          {page}
        </Pagination.Item>
      );
    }

    // Add ellipsis at end if needed
    if (endPage < totalPages) {
      items.push(<Pagination.Ellipsis key="ellipsis-end" disabled />);
    }

    items.push(
      <Pagination.Next key="next" onClick={() => handlePageChange(currentPage + 1)} disabled={currentPage === totalPages} />
    );
    items.push(
      <Pagination.Last key="last" onClick={() => handlePageChange(totalPages)} disabled={currentPage === totalPages} />
    );

    return items;
  };

  // --- Render Logic ---

  if (selectedVideoId) {
    return <VideoDetailView videoId={selectedVideoId} onBack={() => setSelectedVideoId(null)} />;
  }

  let content;
  if (loading) {
    content = (
      <div className="text-center">
        <Spinner animation="border" role="status">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    );
  } else if (error) {
    content = <Alert variant="danger">{error}</Alert>;
  } else if (videos.length === 0) {
    content = <p>No videos have been added to the library yet.</p>;
  } else {
    content = (
      <>
        {/* Pagination at top */}
        <div className="d-flex justify-content-end mb-4">
          <Pagination>{renderPaginationItems()}</Pagination>
        </div>

        {/* Video cards */}
        <div className="d-flex flex-column gap-3">
          {videos.map(video => (
            <Card 
              key={video.id} 
              className="video-list-item-card is-clickable"
              onClick={() => setSelectedVideoId(video.id)}
            >
              <Row className="g-0">
                {/* Thumbnail Column */}
                <Col md={4} lg={3} className="d-flex align-items-center">
                  <Card.Img src={getProxyUrl(video.thumbnail_url)} className="video-list-thumbnail" />
                </Col>

                {/* Details Column */}
                <Col md={8} lg={9}>
                  <Card.Body>
                    <Card.Title className="mb-2">{video.title}</Card.Title>
                    <Card.Subtitle className="mb-2 text-muted">{video.channel_title}</Card.Subtitle>
                    
                    <div className="d-flex justify-content-between align-items-center mt-3">
                      <small className="text-muted">
                        {formatDate(video.published_at)} &bull; {formatDuration(video.duration)}
                      </small>
                      {video.downloaded ? (
                        <Badge bg="success">Downloaded</Badge>
                      ) : (
                        <Badge bg="secondary">Not Downloaded</Badge>
                      )}
                    </div>
                  </Card.Body>
                </Col>
              </Row>
            </Card>
          ))}
        </div>

        {/* Pagination at bottom */}
        <div className="d-flex justify-content-end mt-4">
          <Pagination>{renderPaginationItems()}</Pagination>
        </div>
      </>
    );
  }

  return (
    <div>
      <h2 className="mb-4">
        All Videos in Library
        {totalVideos > 0 && <span className="text-muted fs-6 ms-2">({totalVideos} videos)</span>}
      </h2>
      {content}
    </div>
  );
}

export default VideoList;
