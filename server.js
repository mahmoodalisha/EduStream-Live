const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
const server = require('http').Server(app);
const io = require('socket.io')(server);
const { ExpressPeerServer } = require('peer');
const peerServer = ExpressPeerServer(server, { debug: true });
const { v4: uuidV4 } = require('uuid');

app.use('/peerjs', peerServer);
app.set('view engine', 'ejs');
app.use(express.static('public'));

const userDataPath = path.join(__dirname, 'user_data.json');
let userData = {};

fs.readFile(userDataPath, (err, data) => {
  if (err) {
    console.error('Error reading user data:', err);
    return;
  }
  userData = JSON.parse(data);
});

app.get('/', (req, res) => {
  res.sendFile(__dirname + '/templates/classes.html');
});

app.get('/host/:room/:user', (req, res) => {
  const userName = userData[req.params.user] || 'Unknown';
  res.render('host', { roomId: req.params.room, userId: req.params.user, userName, isHost: true });
});

app.get('/user/:room/:user', (req, res) => {
  const userName = userData[req.params.user] || 'Unknown';
  res.render('user', { roomId: req.params.room, userId: req.params.user, userName, isHost: false });
});

app.post('/end-class/:room', (req, res) => {
  const roomId = req.params.room;
  io.to(roomId).emit('class-ended');
  res.redirect('/');
});

let currentRoomId;
const rooms = {};

io.on('connection', socket => {
  socket.on('create-room', roomId => {
    currentRoomId = roomId;
    rooms[roomId] = { count: 0 }; // Initialize room with a count of 0
  });

  socket.on('get-room', callback => {
    callback(currentRoomId);
  });

  socket.on('user-click', roomId => {
    if (rooms[roomId]) {
      rooms[roomId].count += 1;
      io.emit('update-click-count', rooms[roomId].count); // Update all clients with the new count
    }
  });

  socket.on('join-room', (roomId, userId, isHost) => {
    socket.join(roomId);
    if (isHost) {
      socket.to(roomId).emit('host-connected', userId);
    } else {
      socket.to(roomId).emit('user-connected', userId);
    }

    // Increment participant count and emit update
    if (!rooms[roomId]) {
      rooms[roomId] = { count: 1 }; // Initialize room with a count of 1
    } else {
      rooms[roomId].count += 1;
    }
    io.to(roomId).emit('update-participant-count', rooms[roomId].count);

    // Handle poll creation
    socket.on('create-poll', poll => {
      io.to(roomId).emit('poll', poll);
    });

    // Handle poll answer
    socket.on('answer-poll', answer => {
      io.to(roomId).emit('poll-answer', answer);
    });

    // Handle messages
    socket.on('message', message => {
      io.to(roomId).emit('createMessage', message);
    });

    socket.on('disconnect', () => {
      if (isHost) {
        socket.to(roomId).emit('host-disconnected', userId);
      } else {
        socket.to(roomId).emit('user-disconnected', userId);
      }

      // Decrement participant count and emit update
      if (rooms[roomId]) {
        rooms[roomId].count -= 1;
        io.to(roomId).emit('update-participant-count', rooms[roomId].count);
      }
    });
  });
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
