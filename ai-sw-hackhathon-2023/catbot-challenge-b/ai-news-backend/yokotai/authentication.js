const msal = require('@azure/msal-node');
require('dotenv').config();

const config = {
  auth: {
    clientId: process.env.APP_CLIENT_ID,
    authority: process.env.AUTHORITY,
    clientSecret: process.env.APP_CLIENT_SECRET,
  },
};

const cca = new msal.ConfidentialClientApplication(config);

const tokenRequest = {
  scopes: [process.env.SCOPE],
};

let accessToken = null;

const getAccessToken = async () => {
    if (!accessToken) {
        const response = await cca.acquireTokenByClientCredential(tokenRequest);
        if (!response || !response.accessToken) {
            console.log("Failed to acquire a token.");
            return null;
        }

        accessToken = response.accessToken;
    }
    return accessToken;
};

module.exports = {
    getAccessToken,
};