export function createSessionRecording() {
    return {
        startTime: null,
        exchanges: [],
        tacticsDetected: [],
        coachingGiven: [],
        metrics: {
            totalTurns: 0,
            userTurns: 0,
            userAudioChunks: 0,
            tacticsUsed: {},
            stallingInstances: 0,
            progressInstances: 0,
            circlingInstances: 0,
            dealClosed: false
        }
    };
}

export function createCostTracker() {
    return {
        audioInputSeconds: 0,
        audioOutputSeconds: 0,
        screenCaptures: 0,
        RATE_AUDIO_INPUT: 0.00025,
        RATE_AUDIO_OUTPUT: 0.001,
        RATE_IMAGE: 0.001315,
        get totalCost() {
            return (this.audioInputSeconds * this.RATE_AUDIO_INPUT) +
                (this.audioOutputSeconds * this.RATE_AUDIO_OUTPUT) +
                (this.screenCaptures * this.RATE_IMAGE);
        }
    };
}
