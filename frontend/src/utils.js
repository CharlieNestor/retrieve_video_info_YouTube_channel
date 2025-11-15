// frontend/src/utils.js

export const getProxyUrl = (url) => {
  if (!url) return '';
  return `http://127.0.0.1:8000/api/image-proxy?url=${encodeURIComponent(url)}`;
};

export const formatDuration = (seconds) => {
  if (seconds === null || seconds === undefined) return 'N/A';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  const hStr = h > 0 ? `${h}:` : '';
  const mStr = m.toString().padStart(2, '0');
  const sStr = s.toString().padStart(2, '0');
  return `${hStr}${mStr}:${sStr}`;
};

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch (e) {
    return dateString;
  }
};
