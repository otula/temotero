import React, { useState } from 'react';
import './App.css';
import GeneratorForm from './GeneratorForm/GeneratorForm';
import GeneratorResult from './GeneratorResult/GeneratorResult';
import { GeneratorOptions, generateNews } from './api/api';

function App() {

    const [data, setData] = useState<string | null>(null);

    const onSubmit = async (options: GeneratorOptions) => {
        setData("Loading...");
        const data = await generateNews(options);
        setData(data.message);
    };

    return (
        <div className="App">
            <h1>News Generator</h1>
            <GeneratorForm onSubmit={onSubmit}/>
            <GeneratorResult result={data}/>
        </div>
    );
}

export default App;
