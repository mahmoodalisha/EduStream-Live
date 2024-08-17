const socket = io('/');
const videoGrid = document.getElementById('video-grid');
const myPeer = new Peer(undefined, {
  path: '/peerjs',
  host: '/',
  port: '5000'
});
let myVideoStream;
const myVideo = document.createElement('video');
myVideo.muted = true;
const peers = {};

const getUserIdFromUrl = () => {
  const path = window.location.pathname;
  const match = path.match(/\/(host|user)\/([^\/]+)\/([^\/]+)$/);
  return match ? match[3] : null;
};

const getRoomIdFromUrl = () => {
  const path = window.location.pathname;
  const match = path.match(/\/(host|user)\/([^\/]+)\/([^\/]+)$/);
  return match ? match[2] : null;
};

const getRoleFromUrl = () => {
  const path = window.location.pathname;
  const match = path.match(/\/(host|user)\/[^\/]+\/[^\/]+$/);
  return match ? match[1] : null;
};

const userId = getUserIdFromUrl();
const roomId = getRoomIdFromUrl();
const role = getRoleFromUrl();

const fetchUserName = async (userId) => {
  try {
    const response = await fetch(`http://127.0.0.1:5000/getUserName/${userId}`);
    const data = await response.json();
    return data.username || 'unknown';
  } catch (error) {
    console.error('Error fetching username:', error);
    return 'unknown';
  }
};

const displayUserName = async (userId) => {
  const userName = await fetchUserName(userId);
  return userName || 'unknown';
};

navigator.mediaDevices.getUserMedia({
  video: true,
  audio: true
}).then(stream => {
  myVideoStream = stream;
  addVideoStream(myVideo, stream);

  myPeer.on('call', call => {
    call.answer(stream);
    const video = document.createElement('video');
    call.on('stream', userVideoStream => {
      addVideoStream(video, userVideoStream);
    });
  });

  socket.on('user-connected', userId => {
    connectToNewUser(userId, stream);
  });

  socket.on('host-connected', userId => {
    connectToNewUser(userId, stream);
  });

  socket.on('update-participant-count', count => {
    document.getElementById('participant-count').textContent = count;
  });

  $('html').keydown(async function (e) {
    if (e.which == 13 && $("input").val().length !== 0) {
      const message = $("input").val();
      const userName = await displayUserName(userId);
      socket.emit('message', { message, userName });
      $("input").val('');
    }
  });

  socket.on("createMessage", ({ message, userName }) => {
    $("ul").append(`<li class="message"><b>${userName}</b><br/>${message}</li>`);
    scrollToBottom();
  });
  
  socket.on('poll', poll => {
    const ul = document.querySelector('.messages');
    const li = document.createElement('li');
    li.appendChild(document.createTextNode(`Poll: ${poll}`));
    ul.appendChild(li);
  });

  socket.on('poll-answer', answer => {
    const ul = document.querySelector('.messages');
    const li = document.createElement('li');
    li.appendChild(document.createTextNode(`Answer: ${answer}`));
    ul.appendChild(li);
  });

  // Handle messages
  socket.on('message', (message) => {
    // send message to the same room
    io.to(roomId).emit('createMessage', message);
  });

}).catch(error => {
  console.error('Error accessing media devices.', error);
});

socket.on('user-disconnected', userId => {
  if (peers[userId]) peers[userId].close();
});

myPeer.on('open', id => {
  socket.emit('join-room', roomId, userId, role);
});

function connectToNewUser(userId, stream) {
  const call = myPeer.call(userId, stream);
  const video = document.createElement('video');
  call.on('stream', userVideoStream => {
    addVideoStream(video, userVideoStream);
  });
  call.on('close', () => {
    video.remove();
  });

  peers[userId] = call;
}

function addVideoStream(video, stream) {
  video.srcObject = stream;
  video.addEventListener('loadedmetadata', () => {
    video.play();
  });
  videoGrid.append(video);
}

const scrollToBottom = () => {
  var d = $('.main__chat_window');
  d.scrollTop(d.prop("scrollHeight"));
};

const muteUnmute = () => {
  const enabled = myVideoStream.getAudioTracks()[0].enabled;
  if (enabled) {
    myVideoStream.getAudioTracks()[0].enabled = false;
    setUnmuteButton();
  } else {
    setMuteButton();
    myVideoStream.getAudioTracks()[0].enabled = true;
  }
};

const playStop = () => {
  let enabled = myVideoStream.getVideoTracks()[0].enabled;
  if (enabled) {
    myVideoStream.getVideoTracks()[0].enabled = false;
    setPlayVideo();
  } else {
    setStopVideo();
    myVideoStream.getVideoTracks()[0].enabled = true;
  }
};

const setMuteButton = () => {
  const html = `
    <i class="fas fa-microphone"></i>
    <span>Mute</span>
  `;
  document.querySelector('.main__mute_button').innerHTML = html;
};

const setUnmuteButton = () => {
  const html = `
    <i class="unmute fas fa-microphone-slash"></i>
    <span>Unmute</span>
  `;
  document.querySelector('.main__mute_button').innerHTML = html;
};

const setStopVideo = () => {
  const html = `
    <i class="fas fa-video"></i>
    <span>Stop Video</span>
  `;
  document.querySelector('.main__video_button').innerHTML = html;
};

const setPlayVideo = () => {
  const html = `
    <i class="stop fas fa-video-slash"></i>
    <span>Play Video</span>
  `;
  document.querySelector('.main__video_button').innerHTML = html;
};

// Poll option click event
document.querySelectorAll('.poll-option').forEach(option => {
  option.addEventListener('click', function() {
      document.querySelectorAll('.poll-option').forEach(opt => opt.classList.remove('selected'));
      this.classList.add('selected');
      socket.emit('answer-poll', this.getAttribute('data-option'));
  });
});

// Send message on button click
document.getElementById('send_message').addEventListener('click', () => {
  const message = document.getElementById('chat_message').value;
  if (message) {
    socket.emit('message', message);
    document.getElementById('chat_message').value = '';
  }
});

// Send poll on button click (for host)
if (IS_HOST) {
  document.getElementById('send_poll').addEventListener('click', () => {
    const pollText = document.getElementById('poll_message').value;
    if (pollText) {
      socket.emit('create-poll', pollText);
      document.getElementById('poll_message').value = '';
    }
  });
}

// Speech-to-text for poll creation
if ('webkitSpeechRecognition' in window) {
  const SpeechRecognition = window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();

  recognition.continuous = false;
  recognition.interimResults = false;

  // Poll speech recognition
  document.getElementById('start_poll_speech').addEventListener('click', () => {
    recognition.start();
  });

  recognition.onresult = (event) => {
    const speechResult = event.results[0][0].transcript;
    document.getElementById('poll_message').value = speechResult;
  };

  recognition.onspeechend = () => {
    recognition.stop();
  };

  recognition.onerror = (event) => {
    console.error('Speech recognition error', event);
  };
} else {
  console.warn('Speech recognition not supported in this browser.');
}

// Handle end class button click
document.getElementById('end-class-btn').addEventListener('click', () => {
  fetch(`/end-class/${ROOM_ID}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    }
  })
  .then(response => {
    if (response.ok) {
      console.log('Request successful');
      window.location.href = '/';
    } else {
      console.error('Response error:', response.status);
    }
  })
  .catch(error => {
    console.error('Error ending class:', error);
  });
});

// Handle leave class button click (if this button has a different function)
document.getElementById('leave-class-btn').addEventListener('click', () => {
  console.log('Leave Class button clicked'); // Debugging log
  window.location.href = '/';
});

// Add a new event listener for participant count
socket.on('update-participant-count', count => {
  document.getElementById('participant-count').textContent = count;
});
