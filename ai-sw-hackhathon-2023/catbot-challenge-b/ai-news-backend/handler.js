const makeNew = require("./yokotai").makeNew;

const notFound = (response) => {
    // Send not found response
    response.writeHead(404, {"Content-Type": "application/json"});
    response.write(JSON.stringify({ message: "Not found" }));
    response.end();
};

const handler = (request, response) => {

    const { url, headers, method } = request;

    if (method === "POST") {
        // Extract the body from the request
        let body = [];
        request.on("data", (chunk) => {
            body.push(chunk);
        }).on("end", () => {
            body = JSON.parse(Buffer.concat(body).toString());
            console.log(body);

            // Add generate endpoint
            if (url === "/generate") {
                makeNew(body.sourceUrl, body.topic).then((message) => {
                    response.writeHead(200, {"Content-Type": "application/json"});
                    response.write(JSON.stringify({ message }));
                    response.end();
                    return;
                });
            } else {
                notFound(response);
                return;
            }
        });
        return;
    }

    notFound(response);
    return;

};

module.exports = handler;