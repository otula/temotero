
export type GeneratorOptions = {
    sourceUrl: string;
    topic: string;
    language: string;
};

export type GeneratorResponse = {
    message: string;
}

export const generateNews = async (options: GeneratorOptions): Promise<GeneratorResponse> => {
    const response = await fetch('/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(options),
    });

    return response.json() as Promise<GeneratorResponse>;
}