const axios = require('axios');
const { getAccessToken } = require('./authentication');
const FormData = require('form-data');

const getDocuments = async () => {
    const accessToken = await getAccessToken();
    const response = await axios.get(`${process.env.API_URL}documents`, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const addTag = async (tag) => {
    const accessToken = await getAccessToken();
    const response = await axios.post(`${process.env.API_URL}tags`,
        { "name": tag },
        {
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        }
    );
    return response.data;
}

const getTags = async () => {
    const accessToken = await getAccessToken();
    const response = await axios.get(`${process.env.API_URL}tags`, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const addDocument = async (tagId, url, depth = 0) => {
    const accessToken = await getAccessToken();

    const formData = new FormData();

    const data = {
        "tags": [tagId],
        "url": url,
        "maxdepth": depth,
        "maxexternaldepth": 0,
        "rooturl": ""
    };

    formData.append('data', JSON.stringify(data));

    const response = await axios.post(`${process.env.API_URL}documents`,
        formData,
        {
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        }
    );

    return response.data;

}

const createChat = async (name, tags) => {
    const accessToken = await getAccessToken();
    const response = await axios.post(`${process.env.API_URL}/chats`, {
        "tags": tags,
        "name": name,
        "use_internal_data": true
    }, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const getChat = async (id) => {
    const accessToken = await getAccessToken();
    const response = await axios.get(`${process.env.API_URL}/chats/${id}`, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const updateChat = async (id, name, tags) => {
    const accessToken = await getAccessToken();
    const response = await axios.put(`${process.env.API_URL}/chats/${id}`, {
        "tags": tags,
        "name": name,
        "use_internal_data": true
    }, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const deleteChat = async (id) => {
    const accessToken = await getAccessToken();
    const response = await axios.delete(`${process.env.API_URL}/chats/${id}`, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const getChats = async () => {
    const accessToken = await getAccessToken();
    const response = await axios.get(`${process.env.API_URL}/chats`, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const createMessage = async (chatId, content) => {
    const accessToken = await getAccessToken();
    const response = await axios.post(`${process.env.API_URL}/messages`, {
        "content": content,
        "chat_id": chatId,
        "instructions": "string",
    }, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
    });
    return response.data;
}

const getAllMessages = async (chatId) => {
    const accessToken = await getAccessToken();
    const response = await axios.get(`${process.env.API_URL}/messages`, {
        headers: {
            Authorization: `Bearer ${accessToken}`,
        },
        params: {
            chat_id: chatId,
        },
    });
    return response.data;
}

const waitDocument = async (docId) => {
    const accessToken = await getAccessToken();

    return new Promise(async (resolve) => {
        const tryGetDocument = async () => {
            console.log("Trying to get document", docId);
            let doc;
            try {
                doc = await axios.get(`${process.env.API_URL}/documents/${docId}?raw=true`, {
                    headers: {
                        Authorization: `Bearer ${accessToken}`,
                    },
                });
                console.log(doc.data)
            } catch (e) {
                console.log("Error in getDoc: ", e.message);
            }
            
            if (doc.data["raw_text"] !== "") {
                console.log("Document ready");
                resolve(true);
            } else {
                console.log("Waiting for doc...");
                setTimeout(async () => {
                    tryGetDocument();
                }, 3000);
            }
        };

        tryGetDocument();
    });


}

module.exports = {
    getDocuments,
    getChat,
    createChat,
    updateChat,
    deleteChat,
    getChats,
    createMessage,
    getAllMessages,
    addDocument,
    getTags,
    addTag,
    waitDocument,
};

