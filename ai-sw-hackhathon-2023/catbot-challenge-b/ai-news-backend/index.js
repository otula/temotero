const http = require('http');
const handler = require('./handler');

http.createServer(handler).listen(5000);

console.log("Listening on port 5000!");