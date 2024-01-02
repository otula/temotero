import React, { useState } from 'react';
import { GeneratorOptions } from '../api/api';

type GeneratorFormProps = {
    onSubmit: (options: GeneratorOptions) => void;
};

const GeneratorForm = ({ onSubmit }: GeneratorFormProps) => {
    // State variables for form inputs
    const [sourceUrl, setSourceUrl] = useState('');
    const [topic, setTopic] = useState('');
    const [language, setLanguage] = useState('FI');

    // Function to handle form submission
    const handleSubmit = (e: any) => {
        e.preventDefault();

        onSubmit({sourceUrl, topic, language })
        console.log('Form submitted:', { sourceUrl, topic, language });
    };

    return (
        <div
            style={{ 
                display: 'flex',
                flexDirection: 'column',
                width: "100%",
                alignItems: 'center',
            }}
        >
            <form 
                onSubmit={handleSubmit} 
                style={{ 
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    width: 'fit-content',
                }}
            >
                <label>
                    Source URL:
                    <input
                        type="text"
                        value={sourceUrl}
                        onChange={(e) => setSourceUrl(e.target.value)}
                    />
                </label>
                <br />
                <label>
                    Topic:
                    <input
                        type="text"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                    />
                </label>
                <br />
                <label>
                    Language:
                    <select
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                    >
                        <option value="FI">FI</option>
                        <option value="EN">EN</option>
                        <option value="SV">SV</option>
                    </select>
                </label>
                <br />
                <button type="submit">Submit</button>
            </form>
        </div>
    );
};

export default GeneratorForm;
