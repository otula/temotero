import React from 'react';

type GeneratorResultProps = {
    result: string | null;
};

const GeneratorResult = ({ result }: GeneratorResultProps) => {
    if (!result) return null;

    return (
        <div>
            <h2>Your result:</h2>
            {result}
        </div>
    );
}

export default GeneratorResult;