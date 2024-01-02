/**
 * TODO(developer): Uncomment these variables before running the sample.\
 * (Not necessary if passing values as arguments)
 */
const project = 'news-generator-406918';
const location = 'europe-west';
const aiplatform = require('@google-cloud/aiplatform');
process.env['GOOGLE_APPLICATION_CREDENTIALS'] = './news_generator_key.json';

// Imports the Google Cloud Prediction service client
const {PredictionServiceClient} = aiplatform.v1;

// Import the helper module for converting arbitrary protobuf.Value objects.
const {helpers} = aiplatform;

// Specifies the location of the api endpoint
const clientOptions = {
  apiEndpoint: 'us-central1-aiplatform.googleapis.com',
};

const publisher = 'google';
const model = 'text-bison@001';

// Instantiates a client
const predictionServiceClient = new PredictionServiceClient(clientOptions);

async function callPredict() {
  // Configure the parent resource
  const endpoint = `projects/${project}/locations/${location}/publishers/${publisher}/models/${model}`;

  const prompt = {
    prompt:
      'Sort the following words alphabetically: tomato, cat and apple',
  };
  const instanceValue = helpers.toValue(prompt);
  const instances = [instanceValue];

  const parameter = {
    temperature: 0.2,
    maxOutputTokens: 256,
    topP: 0.95,
    topK: 40,
  };
  const parameters = helpers.toValue(parameter);

  const request = {
    endpoint,
    instances,
    parameters,
  };

  // Predict request
  const response = await predictionServiceClient.predict(request);
  
  console.log('Get text prompt response');
  console.log(response);
  
  const prediction = response[0].predictions[0];
  console.log("Prediction");
  console.log(JSON.stringify(prediction, null, 2));
}

callPredict();