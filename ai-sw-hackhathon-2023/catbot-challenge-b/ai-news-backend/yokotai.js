const {addTag, addDocument, getDocument, getDocuments, getChat, createChat, updateChat, deleteChat, getChats, getAllMessages, createMessage, waitDocument} = require('./yokotai/api');

const makeNew = async (url, topic, language='finnish') => {

    const newTag = await addTag("catbot-" + Date.now());
    console.log(newTag);

    const tagId = newTag.id;
    
    const newDoc = await addDocument(tagId, url);
    console.log(newDoc);


    const docReady = await waitDocument(newDoc.id);

    const newChat = await createChat("CatBotChat"+Date.now(), [newTag.id]);
    console.log(newChat);

    // const chat = await getChat(newChat.id);
    // //console.log(chat);

    const message = await createMessage(newChat.id, topic);
    //console.log(message);
    const messages = await getAllMessages(newChat.id);
    

    return messages[1].content;
};

module.exports = {
    makeNew
};