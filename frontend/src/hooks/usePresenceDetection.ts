import { useCallback, useRef, useEffect, useState } from "react";
import {
  FaceLandmarker,
  PoseLandmarker,
  FilesetResolver,
} from "@mediapipe/tasks-vision";

export interface PresenceMetrics {
  eye_contact: number;
  posture: number;
  tension: number;
  dominant_emotion: string;
}

interface UsePresenceDetectionOptions {
  onMetrics: (metrics: PresenceMetrics) => void;
  fps?: number;
}

export function usePresenceDetection({ onMetrics, fps = 5 }: UsePresenceDetectionOptions) {
  const [isReady, setIsReady] = useState(false);
  const [isRunning, setIsRunning] = useState(false);

  const faceLandmarkerRef = useRef<FaceLandmarker | null>(null);
  const poseLandmarkerRef = useRef<PoseLandmarker | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastProcessTimeRef = useRef<number>(0);

  const initialize = useCallback(async () => {
    try {
      const vision = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
      );

      const [faceLandmarker, poseLandmarker] = await Promise.all([
        FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          numFaces: 1,
          outputFaceBlendshapes: true,
          outputFacialTransformationMatrixes: true,
        }),
        PoseLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
            delegate: "GPU",
          },
          runningMode: "VIDEO",
          numPoses: 1,
        }),
      ]);

      faceLandmarkerRef.current = faceLandmarker;
      poseLandmarkerRef.current = poseLandmarker;
      setIsReady(true);
      console.log("[MediaPipe] Face and Pose Landmarkers initialized");
    } catch (err) {
      console.error("[MediaPipe] Failed to initialize:", err);
    }
  }, []);

  useEffect(() => {
    initialize();
    return () => {
      faceLandmarkerRef.current?.close();
      poseLandmarkerRef.current?.close();
    };
  }, [initialize]);

  const calculateEyeContact = useCallback(
    (faceLandmarks: { x: number; y: number; z: number }[]): number => {
      if (!faceLandmarks || faceLandmarks.length < 478) return 50;

      // Iris landmarks: left (468-472), right (473-477)
      // Eye corner landmarks: left outer (33), left inner (133), right inner (362), right outer (263)
      const leftIrisCenter = faceLandmarks[468];
      const rightIrisCenter = faceLandmarks[473];
      const leftOuter = faceLandmarks[33];
      const leftInner = faceLandmarks[133];
      const rightInner = faceLandmarks[362];
      const rightOuter = faceLandmarks[263];

      // Calculate horizontal position of iris within eye (0 = looking left, 1 = looking right)
      const leftEyeWidth = Math.abs(leftInner.x - leftOuter.x);
      const rightEyeWidth = Math.abs(rightOuter.x - rightInner.x);

      const leftIrisPosition = (leftIrisCenter.x - leftOuter.x) / leftEyeWidth;
      const rightIrisPosition = (rightIrisCenter.x - rightInner.x) / rightEyeWidth;

      // Average position (0.5 = looking straight)
      const avgPosition = (leftIrisPosition + rightIrisPosition) / 2;

      // Calculate deviation from center (0 = perfect center, 0.5 = looking fully away)
      const deviation = Math.abs(avgPosition - 0.5);

      // Also check vertical gaze (nose tip vs iris position)
      const noseTip = faceLandmarks[1];
      const avgIrisY = (leftIrisCenter.y + rightIrisCenter.y) / 2;
      const verticalDeviation = Math.abs(avgIrisY - noseTip.y) * 2;

      // Combined score (100 = perfect eye contact, 0 = looking away)
      const horizontalScore = Math.max(0, 100 - deviation * 200);
      const verticalScore = Math.max(0, 100 - verticalDeviation * 100);

      return Math.round((horizontalScore * 0.7 + verticalScore * 0.3));
    },
    []
  );

  const calculatePosture = useCallback(
    (poseLandmarks: { x: number; y: number; z: number; visibility?: number }[]): number => {
      if (!poseLandmarks || poseLandmarks.length < 12) return 70;

      // Key landmarks: shoulders (11, 12), ears (7, 8), nose (0)
      const leftShoulder = poseLandmarks[11];
      const rightShoulder = poseLandmarks[12];
      const nose = poseLandmarks[0];

      // Check if landmarks are visible enough
      const visibility = Math.min(
        leftShoulder.visibility ?? 0,
        rightShoulder.visibility ?? 0,
        nose.visibility ?? 0
      );
      if (visibility < 0.5) return 70;

      // Calculate shoulder tilt (should be close to horizontal)
      const shoulderDy = Math.abs(leftShoulder.y - rightShoulder.y);
      const shoulderDx = Math.abs(leftShoulder.x - rightShoulder.x);
      const shoulderTilt = Math.atan2(shoulderDy, shoulderDx) * (180 / Math.PI);

      // Calculate head forward position (nose should be roughly above shoulders midpoint)
      const shoulderMidX = (leftShoulder.x + rightShoulder.x) / 2;
      const headOffset = Math.abs(nose.x - shoulderMidX);

      // Score calculation
      const tiltScore = Math.max(0, 100 - shoulderTilt * 5);
      const alignmentScore = Math.max(0, 100 - headOffset * 200);

      return Math.round((tiltScore * 0.6 + alignmentScore * 0.4));
    },
    []
  );

  const calculateTension = useCallback(
    (blendshapes: { categoryName: string; score: number }[]): number => {
      if (!blendshapes || blendshapes.length === 0) return 30;

      const getScore = (name: string): number => {
        const shape = blendshapes.find((b) => b.categoryName === name);
        return shape?.score ?? 0;
      };

      // Tension indicators (higher = more tense)
      const browDown = (getScore("browDownLeft") + getScore("browDownRight")) / 2;
      const eyeSquint = (getScore("eyeSquintLeft") + getScore("eyeSquintRight")) / 2;
      const jawClench = 1 - getScore("jawOpen"); // Closed jaw = more tension

      // Relaxation indicators (higher = less tense)
      const smiling = (getScore("mouthSmileLeft") + getScore("mouthSmileRight")) / 2;
      const frowning = (getScore("mouthFrownLeft") + getScore("mouthFrownRight")) / 2;

      // Calculate tension score (0-100, higher = more tense)
      const tensionSignals = browDown * 30 + eyeSquint * 25 + jawClench * 25 + frowning * 20;
      const relaxationBonus = smiling * 30;

      const tension = Math.max(0, Math.min(100, tensionSignals - relaxationBonus));
      return Math.round(tension);
    },
    []
  );

  const detectEmotion = useCallback(
    (blendshapes: { categoryName: string; score: number }[]): string => {
      if (!blendshapes || blendshapes.length === 0) return "neutral";

      const getScore = (name: string): number => {
        const shape = blendshapes.find((b) => b.categoryName === name);
        return shape?.score ?? 0;
      };

      const smiling = (getScore("mouthSmileLeft") + getScore("mouthSmileRight")) / 2;
      const frowning = (getScore("mouthFrownLeft") + getScore("mouthFrownRight")) / 2;
      const browDown = (getScore("browDownLeft") + getScore("browDownRight")) / 2;
      const eyeWide = (getScore("eyeWideLeft") + getScore("eyeWideRight")) / 2;

      // Simple emotion classification
      if (smiling > 0.3) return "positive";
      if (frowning > 0.2 || browDown > 0.3) return "concerned";
      if (eyeWide > 0.3) return "surprised";
      if (browDown > 0.2 && frowning > 0.1) return "frustrated";

      return "neutral";
    },
    []
  );

  const processFrame = useCallback(() => {
    const video = videoRef.current;
    const faceLandmarker = faceLandmarkerRef.current;
    const poseLandmarker = poseLandmarkerRef.current;

    if (!video || !faceLandmarker || !poseLandmarker || video.readyState < 2) {
      animationFrameRef.current = requestAnimationFrame(processFrame);
      return;
    }

    const now = performance.now();
    const frameInterval = 1000 / fps;

    if (now - lastProcessTimeRef.current < frameInterval) {
      animationFrameRef.current = requestAnimationFrame(processFrame);
      return;
    }

    lastProcessTimeRef.current = now;

    try {
      const timestamp = video.currentTime * 1000;

      const faceResult = faceLandmarker.detectForVideo(video, timestamp);
      const poseResult = poseLandmarker.detectForVideo(video, timestamp);

      let eye_contact = 50;
      let tension = 30;
      let dominant_emotion = "neutral";
      let posture = 70;

      if (faceResult.faceLandmarks && faceResult.faceLandmarks.length > 0) {
        eye_contact = calculateEyeContact(faceResult.faceLandmarks[0]);

        if (faceResult.faceBlendshapes && faceResult.faceBlendshapes.length > 0) {
          tension = calculateTension(faceResult.faceBlendshapes[0].categories);
          dominant_emotion = detectEmotion(faceResult.faceBlendshapes[0].categories);
        }
      }

      if (poseResult.landmarks && poseResult.landmarks.length > 0) {
        posture = calculatePosture(poseResult.landmarks[0]);
      }

      onMetrics({ eye_contact, posture, tension, dominant_emotion });
    } catch (err) {
      console.error("[MediaPipe] Frame processing error:", err);
    }

    animationFrameRef.current = requestAnimationFrame(processFrame);
  }, [fps, onMetrics, calculateEyeContact, calculatePosture, calculateTension, detectEmotion]);

  const start = useCallback(
    (video: HTMLVideoElement) => {
      if (!isReady) {
        console.warn("[MediaPipe] Not ready yet, waiting...");
        return;
      }

      videoRef.current = video;
      setIsRunning(true);
      lastProcessTimeRef.current = 0;
      animationFrameRef.current = requestAnimationFrame(processFrame);
      console.log("[MediaPipe] Started presence detection");
    },
    [isReady, processFrame]
  );

  const stop = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    videoRef.current = null;
    setIsRunning(false);
    console.log("[MediaPipe] Stopped presence detection");
  }, []);

  return {
    start,
    stop,
    isReady,
    isRunning,
  };
}
