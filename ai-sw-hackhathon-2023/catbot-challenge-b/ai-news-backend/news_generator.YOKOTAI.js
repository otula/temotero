const msal = require('@azure/msal-node');
const axios = require('axios');
const path = require('path');


const config = {
  auth: {
    clientId: "", // replace with your APP_CLIENT_ID
    authority: "https://{instance_name}.ciamlogin.com", // replace with your AUTHORITY
    clientSecret: "", // replace with your APP_CLIENT_SECRET
  },
  system: {
    tokenCache: {
      cachePlugin: new msal.extensions.PersistenceCachePlugin(path.join(__dirname, 'msal.cache.json'))
    }
  }
};

const API_URL = "http://localhost:8000/api/v1/"; // replace with your API_URL

const cca = new msal.ConfidentialClientApplication(config);

const tokenRequest = {
  scopes: ["api://{api_app_id}/.default"], // replace with your SCOPES
};

cca.acquireTokenByClientCredential(tokenRequest)
  .then((response) => {
    if (!response || !response.accessToken) {
      console.log("Failed to acquire a token.");
      process.exit();
    }

    console.log(response.accessToken);

    axios.get(API_URL + "chats", {
      headers: { "Authorization": "Bearer " + response.accessToken }
    })
    .then((res) => {
      console.log("API call result: ");
      console.log(JSON.stringify(res.data, null, 2));
    })
    .catch((error) => {
      console.log(error);
    });
  })
  .catch((error) => {
    console.log(error.message);
    console.log(error.errorDescription);
    console.log(error.correlationId);
  });