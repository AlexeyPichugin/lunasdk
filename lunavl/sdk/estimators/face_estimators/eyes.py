"""
Module contains a mouth state estimator

See `eyes`_ and `gaze direction`_.

"""
from enum import Enum
from typing import Union, List, NamedTuple

from FaceEngine import (
    IEyeEstimatorPtr,
    EyeCropper,
    IGazeEstimatorPtr,
    GazeEstimation,
    EyelidLandmarks as CoreEyelidLandmarks,
    EyeAttributes,
    IrisLandmarks as CoreIrisLandmarks,
    State as CoreEyeState,
    EyesEstimation as CoreEyesEstimation,
)  # pylint: disable=E0611,E0401

from lunavl.sdk.errors.errors import LunaVLError
from lunavl.sdk.errors.exceptions import CoreExceptionWrap, LunaSDKException
from lunavl.sdk.base import BaseEstimation, Landmarks
from lunavl.sdk.detectors.facedetector import Landmarks5, Landmarks68
from ..base import BaseEstimator
from ..estimators_utils.extractor_utils import validateInputByBatchEstimator
from ..face_estimators.facewarper import FaceWarp, FaceWarpedImage


class EyeState(Enum):
    """
    Enum for eye states.
    """

    #: eye is opened
    Open = 1
    #: eye is occluded
    Occluded = 2
    #: eye is closed
    Closed = 3

    @staticmethod
    def fromCoreEmotion(coreEyeState: CoreEyeState) -> "EyeState":
        """
        Get enum element by core emotion.

        Args:
            coreEyeState: an eye state form core

        Returns:
            corresponding eye state
        """
        return getattr(EyeState, coreEyeState.name)


class IrisLandmarks(Landmarks):
    """
    Eyelid landmarks.
    """

    #  pylint: disable=W0235
    def __init__(self, coreIrisLandmarks: CoreIrisLandmarks):
        """
        Init

        Args:
            coreIrisLandmarks: core iris landmarks
        """
        super().__init__(coreIrisLandmarks)


class EyelidLandmarks(Landmarks):
    """
    Eyelid landmarks.
    """

    #  pylint: disable=W0235
    def __init__(self, coreEyelidLandmarks: CoreEyelidLandmarks):
        """
        Init

        Args:
            coreEyelidLandmarks: core  eyelid landmarks
        """
        super().__init__(coreEyelidLandmarks)


class Eye(BaseEstimation):
    """
    Eye structure.

    Estimation properties:

        - eyelid
        - iris
    """

    __slots__ = ("irisLandmarks", "eyelidLandMarks", "state")

    #  pylint: disable=W0235
    def __init__(self, coreEstimation: EyeAttributes):
        """
        Init.

        Args:
            coreEstimation: core estimation
        """
        super().__init__(coreEstimation)
        self.irisLandmarks = IrisLandmarks(self._coreEstimation.iris)
        self.eyelidLandMarks = EyelidLandmarks(self._coreEstimation.eyelid)
        self.state = EyeState.fromCoreEmotion(self._coreEstimation.state)

    @property
    def eyelid(self) -> EyelidLandmarks:
        """
        Get eyelid landmarks.

        Returns:
            eyelid landmarks
        """
        return self.eyelidLandMarks

    @property
    def iris(self) -> IrisLandmarks:
        """
        Get iris landmarks.

        Returns:
            iris landmarks
        """
        return self.irisLandmarks

    def asDict(self) -> dict:
        """
        Convert to dict.

        Returns:
            {"iris_landmarks": self.irisLandmarks.asDict(), "eyelid_landmarks": self.eyelidLandMarks.asDict(),
             "state": self.state.name.lower()}
        """
        return {
            "iris_landmarks": self.irisLandmarks.asDict(),
            "eyelid_landmarks": self.eyelidLandMarks.asDict(),
            "state": self.state.name.lower(),
        }


class EyesEstimation(BaseEstimation):
    """
    Eyes estimation structure.

    Attributes:
        leftEye (Eye): estimation for left eye
        rightEye (Eye): estimation for right eye
    """

    __slots__ = ("leftEye", "rightEye")

    def __init__(self, coreEstimation: CoreEyesEstimation):
        """
        Init.

        Args:
            coreEstimation: core estimation
        """
        super().__init__(coreEstimation)
        self.leftEye = Eye(coreEstimation.leftEye)
        self.rightEye = Eye(coreEstimation.rightEye)

    def asDict(self) -> dict:
        """
        Convert to dict.

        Returns:
            {'yaw': self.leftEye, 'pitch': self.rightEye}
        """
        return {"left_eye": self.leftEye.asDict(), "right_eye": self.rightEye.asDict()}


class WarpWithLandmarks(NamedTuple):
    """
    Structure for transferring a detector landmarks estimation and its warp.
    Attributes
        warp (Union[FaceWarp, FaceWarpedImage]): warp core image
        landmarks (Union[Landmarks5, Landmarks68]): landmarks estimation
    """

    warp: Union[FaceWarp, FaceWarpedImage]
    landmarks: Union[Landmarks5, Landmarks68]


class EyeEstimator(BaseEstimator):
    """
    Eye estimator.
    """

    #  pylint: disable=W0235
    def __init__(self, coreEstimator: IEyeEstimatorPtr):
        """
        Init.

        Args:
            coreEstimator: core estimator
        """
        super().__init__(coreEstimator)

    #  pylint: disable=W0221
    @CoreExceptionWrap(LunaVLError.EstimationEyesGazeError)
    def estimate(self, warpWithLandmarks: WarpWithLandmarks) -> EyesEstimation:
        """
        Estimate mouth state on warp.

        Args:WarpWithLandmarks
            warpWithLandmarks: core warp with transformed landmarks

        Returns:
            estimated states
        Raises:
            LunaSDKException: if estimation failed
        """
        cropper = EyeCropper()
        if isinstance(warpWithLandmarks.landmarks, Landmarks5):
            eyeRects = cropper.cropByLandmarks5(
                warpWithLandmarks.warp.warpedImage.coreImage, warpWithLandmarks.landmarks.coreEstimation
            )
        else:
            eyeRects = cropper.cropByLandmarks68(
                warpWithLandmarks.warp.warpedImage.coreImage, warpWithLandmarks.landmarks.coreEstimation
            )
        error, eyesEstimation = self._coreEstimator.estimate(warpWithLandmarks.warp.warpedImage.coreImage, eyeRects)
        if error.isError:
            raise LunaSDKException(LunaVLError.fromSDKError(error))
        return EyesEstimation(eyesEstimation)

    #  pylint: disable=W0221
    @CoreExceptionWrap(LunaVLError.EstimationEyesGazeError)
    def estimateBatch(self, warpWithLandmarksList: List[WarpWithLandmarks]) -> List[EyesEstimation]:
        """
        Batch estimate mouth state on warps.

        Args:
            warpWithLandmarksList: list of core warp with transformed landmarks

        Returns:
            list of estimated states
        Raises:
            LunaSDKException: if estimation failed
            ValueError: if warps count not equals landmarks count
        """
        cropper = EyeCropper()
        eyeRectList = []
        for warpWithLandmarks in warpWithLandmarksList:
            if isinstance(warpWithLandmarks.landmarks, Landmarks5):
                eyeRectList.append(
                    cropper.cropByLandmarks5(
                        warpWithLandmarks.warp.warpedImage.coreImage, warpWithLandmarks.landmarks.coreEstimation
                    )
                )
            else:
                eyeRectList.append(
                    cropper.cropByLandmarks68(
                        warpWithLandmarks.warp.warpedImage.coreImage, warpWithLandmarks.landmarks.coreEstimation
                    )
                )
        coreImages = [row.warp.warpedImage.coreImage for row in warpWithLandmarksList]

        validateInputByBatchEstimator(self._coreEstimator, coreImages, eyeRectList)
        error, eyesEstimations = self._coreEstimator.estimate(coreImages, eyeRectList)

        if error.isError:
            raise LunaSDKException(LunaVLError.fromSDKError(error))
        return [EyesEstimation(eyesEstimation) for eyesEstimation in eyesEstimations]


def _isNotNan(value: float) -> bool:
    """
    Check float is Nan or not
    Args:
        value: float
    Returns:
        value == value
    >>> f = float('nan')
    >>> _isNotNan(f)
    False
    >>> f = float(0.5)
    >>> _isNotNan(f)
    True
    """
    return value == value


class GazeDirection(BaseEstimation):
    """
    Gaze direction structure.
    Estimation properties:

        - yaw
        - pitch
    """

    #  pylint: disable=W0235
    def __init__(self, coreEstimation: GazeEstimation):
        """
        Init.
        """
        super().__init__(coreEstimation)

    @property
    def yaw(self) -> float:
        """
        Get the yaw angle.

        Returns:
            float in range(0, 1)
        """
        return self._coreEstimation.yaw

    @property
    def pitch(self) -> float:
        """
        Get the pitch angle.

        Returns:
            float in range(0, 1)
        """
        return self._coreEstimation.pitch

    def asDict(self) -> dict:
        """
        Convert to dict.

        Returns:
            {'yaw': self.yaw, 'pitch': self.pitch}
        """
        return {
            "yaw": self.yaw if _isNotNan(self.yaw) else None,
            "pitch": self.pitch if _isNotNan(self.pitch) else None,
        }


class WarpWithLandmarks5(NamedTuple):
    """
    Structure for transferring a detector landmarks 5 estimation and its warp.
    Attributes
        warp (Union[FaceWarp, FaceWarpedImage]): warp core image
        landmarks (Landmarks5): landmarks 5 estimation
    """

    warp: Union[FaceWarp, FaceWarpedImage]
    landmarks: Landmarks5


class GazeEstimator(BaseEstimator):
    """
    Gaze direction estimator.
    """

    #  pylint: disable=W0235
    def __init__(self, coreEstimator: IGazeEstimatorPtr):
        """
        Init.

        Args:
            coreEstimator: core estimator
        """
        super().__init__(coreEstimator)

    #  pylint: disable=W0221
    @CoreExceptionWrap(LunaVLError.EstimationEyesGazeError)
    def estimate(self, warpWithLandmarks5: WarpWithLandmarks5) -> GazeDirection:
        """
        Estimate a gaze direction

        Args:
            warpWithLandmarks5: warp with transformed 5 landmarks
        Returns:
            estimated states
        Raises:
            LunaSDKException: if estimation failed
        """
        error, gaze = self._coreEstimator.estimate(
            warpWithLandmarks5.warp.warpedImage.coreImage, warpWithLandmarks5.landmarks.coreEstimation
        )
        if error.isError:
            raise LunaSDKException(LunaVLError.fromSDKError(error))
        return GazeDirection(gaze)

    #  pylint: disable=W0221
    @CoreExceptionWrap(LunaVLError.EstimationEyesGazeError)
    def estimateBatch(self, warpWithLandmarks5List: List[WarpWithLandmarks5]) -> List[GazeDirection]:
        """
        Batch estimate a gaze direction

        Args:
            warpWithLandmarks5List: warp with transformed 5 landmarks list
        Returns:
            list of estimated states
        Raises:
            LunaSDKException: if estimation failed
        """
        images = [row.warp.warpedImage.coreImage for row in warpWithLandmarks5List]
        landmarks = [row.landmarks.coreEstimation for row in warpWithLandmarks5List]
        validateInputByBatchEstimator(self._coreEstimator, images, landmarks)
        error, gazeList = self._coreEstimator.estimate(images, landmarks)

        if error.isError:
            raise LunaSDKException(LunaVLError.fromSDKError(error))
        return [GazeDirection(gaze) for gaze in gazeList]
