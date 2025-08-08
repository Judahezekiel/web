// index.js
const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

const VERIFY_TOKEN = "PrintingWalla"; // Same token you used in Meta dashboard

// GET request for verification (MANDATORY for Meta)
app.get('/', (req, res) => {
  const mode = req.query['hub.mode'];
  const token = req.query['hub.verify_token'];
  const challenge = req.query['hub.challenge'];

  if (mode && token && mode === 'subscribe' && token === VERIFY_TOKEN) {
    console.log("Webhook verified successfully!");
    res.status(200).send(challenge); // Respond with challenge
  } else {
    res.sendStatus(403);
  }
});

// POST request to receive messages (optional for now)
app.post('/', (req, res) => {
  console.log('Received a message from WhatsApp:', JSON.stringify(req.body, null, 2));
  res.sendStatus(200);
});

// Start server
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});

