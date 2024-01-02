const { getDocuments, addDocument, getTags, addTag } = require('./yokotai/api');

(async () => {

    const newTag = await addTag("catbot-" + Date.now());
    console.log(newTag);

    const tagId = newTag.id;
    try {
        const newDoc = await addDocument(tagId, "https://www.tilannehuone.fi/halytys.php");
        console.log(newDoc);
    } catch (e) {
        console.log("Error in addDoc: ", Object.keys(e));
    }

    const documents = await getDocuments();
    console.log(documents);

})();

