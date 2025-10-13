"""
Utility helpers for simulating vehicle tracking data that follow real road
geometry.
"""
from __future__ import annotations

import bisect
import math
from datetime import datetime, timezone
from typing import Dict, List, Sequence, Tuple

BASE_LOCATION: Tuple[float, float] = (23.8103, 90.4125)  # Dhaka, Bangladesh
EARTH_RADIUS_KM = 6371.0088


def _matmul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    return [
        [
            sum(a[i][k] * b[k][j] for k in range(len(b)))
            for j in range(len(b[0]))
        ]
        for i in range(len(a))
    ]


def _transpose(matrix: List[List[float]]) -> List[List[float]]:
    return [list(row) for row in zip(*matrix)]


def _identity(size: int) -> List[List[float]]:
    return [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]


def _invert_2x2(matrix: List[List[float]]) -> List[List[float]]:
    a, b = matrix[0]
    c, d = matrix[1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        # Fall back to pseudo-inverse with small regularisation.
        det = 1e-12
    inv_det = 1.0 / det
    return [[d * inv_det, -b * inv_det], [-c * inv_det, a * inv_det]]


class KalmanFilter2D:
    """
    Lightweight constant-velocity Kalman filter for smoothing GPS traces.
    """

    def __init__(
        self,
        process_variance: float = 5e-7,
        measurement_variance: float = 2e-6,
    ):
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.state: List[float] | None = None  # [lat, lng, v_lat, v_lng]
        self.covariance: List[List[float]] | None = None
        self.last_timestamp: float | None = None

    def step(self, timestamp: float, lat: float, lng: float) -> Tuple[float, float]:
        if self.state is None or self.covariance is None:
            self.state = [lat, lng, 0.0, 0.0]
            self.covariance = [
                [1e-3, 0.0, 0.0, 0.0],
                [0.0, 1e-3, 0.0, 0.0],
                [0.0, 0.0, 1e-2, 0.0],
                [0.0, 0.0, 0.0, 1e-2],
            ]
            self.last_timestamp = timestamp
            return lat, lng

        dt = max(timestamp - (self.last_timestamp or timestamp), 1.0)
        self.last_timestamp = timestamp
        self._predict(dt)
        return self._update(lat, lng)

    def _predict(self, dt: float) -> None:
        if self.state is None or self.covariance is None:
            return

        # State transition.
        lat, lng, v_lat, v_lng = self.state
        lat += dt * v_lat
        lng += dt * v_lng
        self.state = [lat, lng, v_lat, v_lng]

        # Transition matrix.
        A = [
            [1.0, 0.0, dt, 0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
        AT = _transpose(A)

        AP = _matmul(A, self.covariance)
        APA_T = _matmul(AP, AT)

        dt2 = dt * dt
        dt3 = dt2 * dt
        dt4 = dt3 * dt
        q = self.process_variance
        Q = [
            [0.25 * dt4 * q, 0.0, 0.5 * dt3 * q, 0.0],
            [0.0, 0.25 * dt4 * q, 0.0, 0.5 * dt3 * q],
            [0.5 * dt3 * q, 0.0, dt2 * q, 0.0],
            [0.0, 0.5 * dt3 * q, 0.0, dt2 * q],
        ]

        self.covariance = [
            [
                APA_T[row][col] + Q[row][col]
                for col in range(4)
            ]
            for row in range(4)
        ]

    def _update(self, lat: float, lng: float) -> Tuple[float, float]:
        if self.state is None or self.covariance is None:
            return lat, lng

        H = [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ]
        HT = _transpose(H)

        HP = _matmul(H, self.covariance)
        S = _matmul(HP, HT)
        R = [
            [self.measurement_variance, 0.0],
            [0.0, self.measurement_variance],
        ]
        S = [
            [S[row][col] + R[row][col] for col in range(2)]
            for row in range(2)
        ]
        S_inv = _invert_2x2(S)

        PHt = _matmul(self.covariance, HT)
        K = _matmul(PHt, S_inv)  # 4x2

        residual = [
            lat - self.state[0],
            lng - self.state[1],
        ]
        self.state = [
            self.state[i]
            + K[i][0] * residual[0]
            + K[i][1] * residual[1]
            for i in range(4)
        ]

        KH = _matmul(K, H)
        I = _identity(4)
        I_minus_KH = [
            [
                I[row][col] - KH[row][col]
                for col in range(4)
            ]
            for row in range(4)
        ]
        self.covariance = _matmul(I_minus_KH, self.covariance)

        return self.state[0], self.state[1]


# Polylines were generated via OSRM (polyline6 encoding) for well-known Dhaka corridors.
ROUTE_DEFINITIONS: Sequence[Dict[str, str]] = [
    {
        "id": "airport-motijheel",
        "name": "Hazrat Shahjalal Airport → Motijheel",
        "color": "#2563eb",
        "polyline": r"ugynl@__wlkDsF`EcG~A_k@nb@_]qo@qR__@uPiZsXoi@aAuByGuN}@iBaMxJsShPii@|e@i^rXuTvPm`BjnA{i@dc@wJfJqLjLgNbJoLpHiPrI_CW}Au@w@iAWkBBgB`@iAfAiBrQkJpUoNt[eWbp@of@bFwDtp@ig@l_@qX~X}UhSaPbV_SpY{Uvh@ub@pSeQdBuA|KwInm@me@`g@g`@pHcHr\eXfl@_b@h[iOxO{KrJ_HdRqOziAw`A~d@y^|V}PpLeJ`[sW|nA_`AbDgCn^iZlJ_LhHgHtf@ed@rFcG|GaK`EcJbNk`@dHcI`FqDvXuU`t@oh@ns@uj@zYwUlf@{g@zYiWrMmIpKsF~EcCzj@oSj_@eKxb@_J|s@sL`c@{A|mLq`Ax]aEhY}EbTqEdWqG~TuGzRaHlkAsc@~Q{HdIaDjHaC`G_BnLiCbLeBpUcCzX}AzKGxKF~K`@pKv@hJr@fJfA`OrC~NjDfUfHzUhK`SrK`WzQjQnP~G|H`HxIzNlUfFlJlEjKlEnMjFzPhFzRbC`LnBzLzChVpE`j@pF`o@pCxXtDdRxCrL|CzIbDzIpDtInEfIhEbIbFbId]hd@rw@baAxPtXhh@h_A`h@h~@`Ynl@vf@xrAdLlZxLlXz]nq@~k@fhApL`T`M|QdJzKtJtKdHxHdJfItS~O~ObLnTjMrY|MrXdJ`e@zKxHrAjJpAxQdBpsAjKdoAzLxbGlh@~IfA|RzB~\dD~q@nHfaAlJ~p@jIpo@xIfaCb^~WfDhb@hFt}A~Mj}Dt\vOjAtG^zyDz_@zd@`Cbz@|HrcGvj@v`BhOjzAxMtPdB`b@fEp~C|X|vAvLx[`Cr`BxNd`@xC~gApKlI^js@pJv`@~HdSnEvRjD|o@~K|d@~HbTrCha@nEzo@nHry@`ErKD|Ff@nUj@nSn@bTv@ds@lDhp@bF|eA`Ip`@~DrI|@fIjBnFhBvCbBzBrBtD|FvCzFpAdFl@|CX~CPlEC`Ea@fHyBpLeTn}@uLxf@eExNsFjNsKnUqDlIwCbI}AtGk@jEi@xFe@nKBdFNlFt@jThBhg@VbH~A`_@TxEv@rF~@lFvCpKhAx^Z|OBzKl@pKhCvd@xAp_@InBYbFHpMAnJUhGObBs@bFy@bE{@`DgApCo@rAEZ_@hAKZo@fAw@|@{@l@aAd@gAXsBNsBOmBk@aBgAoA}A]u@Yy@Q{@Iu@Eu@DmCLk@n@wBsB{DyBgD{AgA@yAoA_r@[yNa@iR}@}b@As@OcH}D}bECeIBiHFw@VsB`@yA~HmCrBs@fs@aPxBo@|jCou@tWaHljAy\vNcEbjFqyA^}@d@w@jAaAtAm@zAWhB@dB\h@XzGoC~EeBb_@oKhS}Frj@aL`PyDjSqEfyAi\`Dw@vQqEvAa@jm@gM~KuCdc@}KbOuD|QaFzVyFhJwAvJ_BvEw@vl@cH`B{@nA}@dCsDnAiCdAsC^uCL_DIgKySaaAwGi^e@sFRiI}@e@s@u@c@{@WaAIgABeAXwAl@kA~@{@lAe@rAKpAJtPgQ`]o[zMgO~F_IbGqKxH{RjIuVtHaVlA}CbCoGbLkWrMqWlOoXlLoPLOdPsTbEuFtMkLvLsJdOgJrJiEdKuDvFmBlD_AtE_BtDiA|AzEp@l@jAj@~GlCzIhCvH~AjDn@|Dl@|LfAnlAl@taAtBbMBfD?pAEtBGdBEfB[vDeBtDoCdJgIlPeLdNiFjMaFdWqFdy@_I~Y}DtSmC|DgAxBcAlBsA?w@\mBv@_BjAmAb@{DD}ADwDScGa@wEi@mKc@wKQwI@}ZTk`@RiOa@mi@_@sUyBqb@mB{b@_@_PWuG?uTPyr@B_SNcZ_@a]iB}y@g@_LeAkV_@{HGkKToPvAgTz@cFdAeFzBkGtQwa@pYil@dN_YnH{OzBuEvGlDxX`OtKmW",
        "average_speed_kmh": 42.0,
        "origin_label": "Hazrat Shahjalal Intl Airport",
        "destination_label": "Motijheel Commercial Area",
    },
    {
        "id": "mirpur-secretariat",
        "name": "Mirpur DOHS → Bangladesh Secretariat",
        "color": "#0f766e",
        "polyline": r"}x~ll@e}mjkD~Fjr@n`@sFh]iD~@QrKsBpNkChJiBnE}@dDm@xPsDrAUbOmC~Ck@hAStCg@lJeBzL}BjIuAbKiBpJcBpDq@rEy@tJeBhGgAtUeEdJaBjM_CnOoCp_@{G|_@_Hv_@wGzQaDfKqBxMsBfOkCt^mGbHmA~^qG~OqE`^}GrEZ|Ds@jSmDd_@qGpIyAhReDfCc@jLqBhB[jDm@dDm@p@Mt\wG~_@}G~`@}Hd^}Fho@_MbUwEHeBf@{A~@gAiEoXgAwWRmSfCs]nGoc@xAuPfHgi@fDsUxLay@n@cEv@kHtHig@zAyFfIwZlKoVhPkZbYa`@xQeXzGcJdNoPbEaFpPqSlAsAdAmAr^md@x[ia@vlAo_Bzk@yu@|NqWxSeb@zIaTpQ{g@jTat@vUsw@xh@olBvJif@dC}K^q@~@m@zAUv@KlBElPYbPa@vCQtRoAhMeB`TkE`^{D|[mCbAKfPwA|^iDt^sDx]mDvRq@|MTdMbAtIXtIj@rk@`CxJb@bWHnJu@xYaCxCm@jC{Ah@}A\eAi@}RIsC]aHWqEiA{SS}D{B{a@AeFAmCDg@v@}H|[}cBH{FpDtAppA|]rHzAvQdCxDd@lZnCtRpBrL~A~LhC~MrCz_Cdl@xQvEdo@jNnTzDfQzC~Q~AzUzAj_@hAzy@z@bz@dAlfAcAf\{Af\gCb}@{FfeByLbCQ|FaAxBo@rEsAl@Xv@J|DQlxAuJtNGbSbArRdBz_@bD~kA`NlD`@nCZj\nErh@lEjL~@fU~AtUxBdIz@lEn@hIlBbKx@~BPrd@hDpUl@bSVje@jBnOVrPTn^t@vBErNWtBE|Ni@`M]vL@rDEvS]h]gBzJm@xXqAdj@kCtn@cE|x@qIhOaCzj@yIxDcAbDwA~HmCrBs@fs@aPxBo@|jCou@tWaHljAy\vNcEbjFqyA^}@d@w@jAaAtAm@zAWhB@dB\h@XzGoC~EeBb_@oKhS}Frj@aL`PyDjSqEfyAi\`Dw@vQqEvAa@jm@gM~KuCdc@}KbOuD|QaFzVyFhJwAvJ_BvEw@vl@cHhFg@tO{ApD_@dFc@tR_BzGUhGIlEThOlAnOt@fSj@`Pd@zSXn^h@bJl@dO|@jBJfBTn_@pE~Dt@jJhArRnBlMzArBHzOl@fIXnXVvDDrIN`A@hf@I~c@IdTSzu@yDhLkAvEcAdA{@rAe@zYyW`MuN~MgM`CcC",
        "average_speed_kmh": 35.0,
        "origin_label": "Mirpur DOHS",
        "destination_label": "Bangladesh Secretariat",
    },
    {
        "id": "narayanganj-gulshan",
        "name": "Narayanganj River Port → Gulshan 2",
        "color": "#9333ea",
        "polyline": r"qf{`l@_hzrkDC{Am@uDa@}@aAo@iMIoCUyYz@`Ffj@|A`LbK|m@rNxu@lDzL~CfH|BPjBjAj@z@\dAJjAAjAShAk@pAaA~@cDrFmGtU_@lEuAdc@aAfI_DvZ}Ir]{AjCgJzf@}Gfc@gKfp@kL`e@wDzKsNza@}Mr^_BjEmNjc@cDlI_KlWwKl]gDfKiF~QwJvY{M~a@aR|e@{Qnd@cNhc@oGbTmC|IuCjNwArPyAx[aCra@wD~[uSj}@yJ`_@w@pC}HjW}FdPuFzQcMna@oHt[}AfHaDzM{Hd[wFjXyG|[aHj^uAfFcHjWgDtL{GfVi@bBwPvi@mQra@iJfQiBvDa]~j@gLzSkFpJaN|DoHvBg[vGob@~Iq\bIoa@nMm_@`KqQlFiFjAyNxEsJtC{IpCwQtGwDxAea@~OmE`B{NxEcOlFcQzGsV`K}UnI{EhA_G`B}FrAsOpDiWzEuWpAsP`AsPFgQh@qVv@uq@xGwFv@qObH_ErFoYjb@aKvNqd@zk@}JfKwOzP{IvKsHxGcDvBoBhAgE~AoCr@wGvAsTxDg[fFuLtBeJzCuL~DmMfG}NpKoCtB}BjC_KjKyXn_@oPxPc[bZ{QbOsT`Lga@bR}\|Q{g@x\ue@t\em@n\g_@xWoVhUuTrVmQfRgOrPyGvHeWfUwM`Kid@fa@us@pm@oZxWeP~LcE~EcVlSiQbSySzUmT|WcVdZ}T~XaLfMuVfV{TvSgNtLkYjU_OrPcTzPgIvF_JnGoDpEuH`LwGpMiDzHaD|GcC~CqEjDqFnDaLfFmNjFiUhImQ|G{a@xNmj@xX{\tQiQhRmYj\ch@|l@uZx\w`@j]ac@~]c^vYa\|_@gYxYcMpH_MtBeZnBy^j@wKNwNhBi[zEs`@~L{ZrOeN`LsIbHyUbSu^~ZqgA~fA_NlSqG~G{IjJgMfM{MfM{K~H{GzFgCpCcDvEkDnFa]tf@wCtGiC`EiNdSaX`^wJlMaG~HsQjTsElHiClDkHvJim@`y@wDfFyLhNaErF{Yfc@{pAhmB{Wnb@wHjMsKjOwGtHeI~GkOxGkHpCoI~AmJ~AaCReV~@wO|BqKpCsOhCyQfHaT~EcGtC_NdJmAnBwJvOm\bi@_HbIyKfMoBzBeBtAsKpK_IrKsF|FyDlEsYdYcf@pb@aF~FmN~MwS~RoJbJwDrGaBrBgBhBu^~]_A`AyBrBaAmAiFmH{BaCsCuCaZ}\cIkKwCwG}CkM_@eAcB{EoCqHsD{HoCaFuKsPuVkb@iTwc@oAuByWm_@}JsK{JkJsM}JcN}HaN{GuC_BCCC?oBo@uRiGeV_HsRuF}RoE}MuA_P}@_Pe@kMOuXb@_t@tEiCTiu@tGaRhAkOzCsF`A_Gd@sVxBeXt@ej@hEgH|@iEb@oi@xDiFd@aKbASH{BLkAMu@Su@a@k@e@g@m@gGt@wStBoMdB}d@pDyb@pC{i@~B}_@|BgmB|KkLd@sWh@wYf@iXLyFHsDh@iFjAwD|AkE~B_EfD}AhBwBxCsBnEqCdLwCjLuD~NgJtj@yTteAwE~VaCbMuCtLwEjO{EbMcJhR}o@fjAkO~Wc{A|cCeM|S_GrMaGpRgC`OsIvZqHdWcD`JqFfMqItOyRv[uE`JaDfI_CzHiBlLgA`Kk@tKqAbR_BvKuBjJyCdJcD~IeBxEsD|EeGdG_EzDwEtDeDrBeSzKe]`RkWnNuUrKg|@r_@{TfKcObImQnLaQjMiQzOyMhRcPnR{FdIuDdGsQz[_E`GsIlPmLnUsHdT}C~I_CtI}@nDmCdMqAlH}@vHoBjSm@bI[~FMpFMpG?`IPza@b@|ZX|MHjHCrI[t[OnNKtPW|PaBjy@iCpuA_Axs@YhYm@zZ}@ji@e@~WoBfhAc@jKg@tHwH|r@aD~RYlBu@pFmGzn@sCj`@_Dfm@_@pBF`@C^K^SV[N]B]E[OSWaDUcDBeDVqDXmCj@aFxAcF`BoEhCiE`C}a@|`@uT`Tg]`[{^hZic@b`@wDfE{L~L}E~Eo`@t`@}@~@kGxGel@zi@kItIcEhEk@j@wD|DsdAfDsRtAeKbA_a@`DkOfAaGeB_Cy@mCkAaDmBaEoDkBcD}BoF?vAStAe@lAc@l@k@d@o@\s@TiAJoAE_AWaAi@u@w@g@cAYkA}DnAmDRaWnAay@hBqmAWeCG{\_@wSSkKm@mx@wHa_@iFiBUmBM}YqAoGKuFGaT?{Vw@g@?eCImXYc]qAmIAuJJ_PdAkHl@aEn@ym@rGiWjDgKjBw[xGaU~FgMvCm`@vJ}_@tHcS~DmW`FyN~DyCt@go@`OknAxWa~@nUoZpJmPpG?vBSzAe@tAu@hAaA|@mAj@sAXkBBiB[}Au@mAoAw@aBa@}B?aCb@}B^}@d@w@jAaAgAcGqEmVcHm^aA{GqCuRyH_a@aCiK}Swp@sk@izA}A{C{q@mjAmQwYmGuLaRy]iC}JwCoJqCaHsDuKmGqOiDgIuA}CiA}BqByBaBuAoBuA{CeCyCiBiDyAqJ_CcDw@sF}@wHw@kDQoBMyCGy]bAsBOiE_@yDq@oD}@mDoAoBoAuBkBuCgDsAkBcDaIiCwFcBuEoA}BsAeB_AaAaB{@eCeA{FkBiI}BiF_AeDe@qD[mEa@cCc@wCk@_Du@iC_AeFkBuEyBaHgDaBkAkPyOiJcIsBiBkByAsAuAmAcBeAqBeO}UiCoEcDqEwBoCkCaDsBiCaByBcB{BwAeCwDkHcJeQuDyGuEwHwNeWcEmHkDoFmCeEeEwFaDmEoOaQaRqPaCoByCiCgA_AiA_AqCkCiEaE_BoAIKqAeAkI}H}KmLsRySeO{PsFyFuJuJ{EsE{@y@iE}CaJcGcFkDuBkB{EgEm@i@eFsEgFwEkIgHkGwEsMaKwIgGyD{B{DgBoFgBoFcBaGwAeGiA{HuAgBU_BK{ADiCN{ARkAh@wBl@}BxAuCtBmCdCsBxAqDlD}BvBkBpB_BlBsClE_CtD_FfJiC`FaBpDoD|HqD~J_ClEgCfFqHbGyEpDkClCaHbHuCdCsBfAsIrBkD`@kF`AuHvAoDNgCG_CGyBa@wBi@cBy@gCaB}B{AiCwBqB{B{AcBkBgCq@yAu@uBo@_Ck@_Ea@iF_@iIIgKGeEByCHqDTsCb@oCr@}CpAkDr@cBpA{ChAaC~@_ClAcCjAaEfAoGx@wFb@eG?yDa@sJg@oGm@sFMiBg@iDiAsDaBaE_BoCq@{@mDuCuDwBmJeDiHeC{E{AiGgB}F{AaKwBuE}@sGaAsKkAoJs@aO_@wJ?{CTmCPwEl@wF|@qGfAqFbAoCd@mVqv@wLmb@oNgb@qK_[_D{HsCcGyEkH_EkEy@u@eE_E}FcEiAy@gGsCcM}CiOqBqNuBo`@iCyf@wCcpA}GqsAaIeEYwTuAmr@sDkUgAmHc@mEi@kEBeQtA}Cn@gPfEeGd@a_@}@wj@mD_ViAow@mEu]cCoV_Age@T_ORmQTaw@tAeU`@oCHgIv@ePpAw]zDeX`Eyc@nF{Y|Dkr@bLoAToMtCsKtCcQtEaM~Bk[lIi\`JuAXguA|_@oSbFge@dNgV~GxBbF",
        "average_speed_kmh": 48.0,
        "origin_label": "Narayanganj River Port",
        "destination_label": "Gulshan 2",
    },
]

VEHICLE_PROFILES: Sequence[Dict[str, str]] = [
    {
        "callsign": "VT-201",
        "license_plate": "DHA-2013",
        "device_id": "VTMS-DHK-201",
        "driver": "Rahim Khan",
        "vehicle_type": "Refrigerated Truck",
    },
    {
        "callsign": "VT-202",
        "license_plate": "DHA-5194",
        "device_id": "VTMS-DHK-202",
        "driver": "Shila Akter",
        "vehicle_type": "Box Van",
    },
    {
        "callsign": "VT-203",
        "license_plate": "DHA-8821",
        "device_id": "VTMS-DHK-203",
        "driver": "Nazmul Islam",
        "vehicle_type": "Flatbed",
    },
    {
        "callsign": "VT-204",
        "license_plate": "DHA-3307",
        "device_id": "VTMS-DHK-204",
        "driver": "Farzana Chowdhury",
        "vehicle_type": "Tanker",
    },
    {
        "callsign": "VT-205",
        "license_plate": "DHA-7742",
        "device_id": "VTMS-DHK-205",
        "driver": "Masud Karim",
        "vehicle_type": "Mini Truck",
    },
    {
        "callsign": "VT-206",
        "license_plate": "DHA-4410",
        "device_id": "VTMS-DHK-206",
        "driver": "Sadia Rahman",
        "vehicle_type": "Delivery Van",
    },
    {
        "callsign": "VT-207",
        "license_plate": "DHA-9145",
        "device_id": "VTMS-DHK-207",
        "driver": "Tariq Ahmed",
        "vehicle_type": "Covered Van",
    },
    {
        "callsign": "VT-208",
        "license_plate": "DHA-6259",
        "device_id": "VTMS-DHK-208",
        "driver": "Mitu Sultana",
        "vehicle_type": "SUV",
    },
    {
        "callsign": "VT-209",
        "license_plate": "DHA-7034",
        "device_id": "VTMS-DHK-209",
        "driver": "Abid Hossain",
        "vehicle_type": "Motorbike",
    },
    {
        "callsign": "VT-210",
        "license_plate": "DHA-5528",
        "device_id": "VTMS-DHK-210",
        "driver": "Shamima Rupa",
        "vehicle_type": "Pickup",
    },
]

GEOFENCES: Sequence[Dict[str, object]] = [
    {
        "id": "motijheel-delivery-zone",
        "name": "Motijheel Delivery Zone",
        "color": "#f97316",
        "points": [
            {"lat": 23.733, "lng": 90.413},
            {"lat": 23.733, "lng": 90.425},
            {"lat": 23.722, "lng": 90.425},
            {"lat": 23.722, "lng": 90.412},
        ],
    },
    {
        "id": "gulshan-priority",
        "name": "Gulshan Priority Service Area",
        "color": "#10b981",
        "points": [
            {"lat": 23.798, "lng": 90.408},
            {"lat": 23.806, "lng": 90.420},
            {"lat": 23.798, "lng": 90.432},
            {"lat": 23.790, "lng": 90.420},
        ],
    },
]

DEPOTS: Sequence[Dict[str, object]] = [
    {
        "id": "uttara-hub",
        "name": "Uttara Logistics Hub",
        "capacity": 52,
        "location": {"lat": 23.874, "lng": 90.398},
    },
    {
        "id": "tejgaon-yard",
        "name": "Tejgaon Service Yard",
        "capacity": 38,
        "location": {"lat": 23.766, "lng": 90.400},
    },
]


def decode_polyline6(polyline: str) -> List[Tuple[float, float]]:
    """
    Decode a polyline6 string into a list of (lat, lng) coordinates.
    """
    coordinates: List[Tuple[float, float]] = []
    index = 0
    lat = 0
    lng = 0
    factor = 1e-6

    while index < len(polyline):
        lat_change, index = _decode_value(polyline, index)
        lng_change, index = _decode_value(polyline, index)
        lat += lat_change
        lng += lng_change
        coordinates.append((lat * factor, lng * factor))

    return coordinates


def _decode_value(polyline: str, index: int) -> Tuple[int, int]:
    result = 0
    shift = 0

    while True:
        if index >= len(polyline):
            raise ValueError("Invalid polyline: buffer exhausted.")
        b = ord(polyline[index]) - 63
        index += 1
        result |= (b & 0x1F) << shift
        shift += 5
        if b < 0x20:
            break

    delta = ~(result >> 1) if (result & 1) else (result >> 1)
    return delta, index


def haversine_km(start: Tuple[float, float], end: Tuple[float, float]) -> float:
    """
    Compute the great-circle distance between two coordinates in kilometres.
    """
    lat1, lng1 = map(math.radians, start)
    lat2, lng2 = map(math.radians, end)
    d_lat = lat2 - lat1
    d_lng = lng2 - lng1
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def _bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Compute forward azimuth in degrees from point 1 to point 2.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lng2 - lng1)

    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        d_lambda
    )
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def _build_routes() -> List[Dict]:
    routes: List[Dict] = []
    for definition in ROUTE_DEFINITIONS:
        coords = decode_polyline6(definition["polyline"])
        if not coords:
            continue

        point_dicts = [{"lat": round(lat, 6), "lng": round(lng, 6)} for lat, lng in coords]
        cumulative: List[float] = [0.0]
        for start, end in zip(coords[:-1], coords[1:]):
            cumulative.append(cumulative[-1] + haversine_km(start, end))

        length_km = cumulative[-1] if cumulative else 0.0
        avg_speed = max(definition.get("average_speed_kmh", 35.0), 5.0)
        loop_seconds = int(max(length_km / avg_speed * 3600, 900))

        origin_lat, origin_lng = coords[0]
        dest_lat, dest_lng = coords[-1]

        routes.append(
            {
                "id": definition["id"],
                "name": definition["name"],
                "color": definition.get("color", "#2563eb"),
                "points": coords,
                "point_dicts": point_dicts,
                "cumulative_km": cumulative,
                "length_km": length_km,
                "average_speed_kmh": avg_speed,
                "loop_seconds": loop_seconds,
                "origin": {
                    "label": definition.get("origin_label", "Origin"),
                    "lat": round(origin_lat, 6),
                    "lng": round(origin_lng, 6),
                },
                "destination": {
                    "label": definition.get("destination_label", "Destination"),
                    "lat": round(dest_lat, 6),
                    "lng": round(dest_lng, 6),
                },
            }
        )
    return routes


ROUTES = _build_routes()
FILTER_STATE: Dict[str, KalmanFilter2D] = {}


def _filter_position(vehicle_key: str, timestamp: float, lat: float, lng: float) -> Tuple[float, float]:
    kalman = FILTER_STATE.get(vehicle_key)
    if kalman is None:
        kalman = KalmanFilter2D()
        FILTER_STATE[vehicle_key] = kalman
    return kalman.step(timestamp, lat, lng)


def generate_vehicle_data(count: int = 10) -> List[Dict]:
    """
    Produce pseudo-real-time vehicle updates moving along mapped routes.
    """
    now = datetime.now(timezone.utc)
    vehicles: List[Dict] = []
    if not ROUTES:
        return vehicles

    for index in range(count):
        route = ROUTES[index % len(ROUTES)]
        loop_seconds = route["loop_seconds"] or 900
        base_speed = route["average_speed_kmh"]

        phase_offset = index * 180  # seconds
        progress_seconds = (now.timestamp() + phase_offset) % loop_seconds
        progress_fraction = progress_seconds / loop_seconds
        target_distance = progress_fraction * route["length_km"]

        raw_lat, raw_lng, segment_index = _interpolate_position(route, target_distance)
        heading = _route_heading(route, segment_index, raw_lat, raw_lng)

        speed_variation = 6 * math.sin((now.timestamp() / 90.0) + index * 0.7)
        speed_kmh = max(base_speed + speed_variation, 8.0)

        remaining_km = max(route["length_km"] - target_distance, 0.02)
        eta_minutes = (remaining_km / max(speed_kmh, 5.0)) * 60

        status = _determine_status(progress_fraction, speed_kmh, base_speed)
        trail_points, upcoming_points = _route_segments(route, segment_index, raw_lat, raw_lng)

        profile = VEHICLE_PROFILES[index % len(VEHICLE_PROFILES)]
        vehicle_key = f"{route['id']}:{profile['device_id']}"
        filtered_lat, filtered_lng = _filter_position(
            vehicle_key,
            now.timestamp(),
            raw_lat,
            raw_lng,
        )

        filtered_point = {"lat": round(filtered_lat, 6), "lng": round(filtered_lng, 6)}
        raw_point = {"lat": round(raw_lat, 6), "lng": round(raw_lng, 6)}
        if trail_points:
            trail_points[-1] = filtered_point
        if upcoming_points:
            upcoming_points[0] = filtered_point

        vehicles.append(
            {
                "id": index + 1,
                "uid": vehicle_key,
                "name": profile["callsign"],
                "fleet_area": route["name"],
                "status": status,
                "speed_kmh": round(speed_kmh, 1),
                "heading": round(heading, 1),
                "location": filtered_point,
                "raw_location": raw_point,
                "trail": trail_points,
                "upcoming": upcoming_points,
                "path": route["point_dicts"],
                "last_update": now.isoformat(),
                "last_update_epoch": now.timestamp(),
                "eta_minutes": round(eta_minutes, 1),
                "identifiers": {
                    "license_plate": profile["license_plate"],
                    "device_id": profile["device_id"],
                    "driver": profile["driver"],
                    "vehicle_type": profile["vehicle_type"],
                },
                "route": {
                    "id": route["id"],
                    "name": route["name"],
                    "color": route["color"],
                    "progress": round(progress_fraction, 3),
                    "distance_km": round(route["length_km"], 2),
                    "origin": route["origin"],
                    "destination": route["destination"],
                },
            }
        )

    return vehicles


def _interpolate_position(route: Dict, distance_km: float) -> Tuple[float, float, int]:
    cumulative = route["cumulative_km"]
    points = route["points"]

    if distance_km <= 0 or len(points) == 1:
        lat, lng = points[0]
        return lat, lng, 0

    if distance_km >= cumulative[-1]:
        lat, lng = points[-1]
        return lat, lng, len(points) - 1

    idx = bisect.bisect_left(cumulative, distance_km)
    if cumulative[idx] == distance_km:
        lat, lng = points[idx]
        return lat, lng, max(idx - 1, 0)

    prev_idx = max(idx - 1, 0)
    start_lat, start_lng = points[prev_idx]
    end_lat, end_lng = points[idx]
    segment_distance = cumulative[idx] - cumulative[prev_idx]
    if segment_distance <= 0:
        return start_lat, start_lng, prev_idx

    ratio = (distance_km - cumulative[prev_idx]) / segment_distance
    lat = start_lat + (end_lat - start_lat) * ratio
    lng = start_lng + (end_lng - start_lng) * ratio
    return lat, lng, prev_idx


def _route_heading(route: Dict, segment_index: int, lat: float, lng: float) -> float:
    points = route["points"]
    next_index = min(segment_index + 1, len(points) - 1)
    next_lat, next_lng = points[next_index]
    if next_index == segment_index:
        prev_index = max(segment_index - 1, 0)
        prev_lat, prev_lng = points[prev_index]
        return _bearing_deg(prev_lat, prev_lng, lat, lng)
    return _bearing_deg(lat, lng, next_lat, next_lng)


def _route_segments(
    route: Dict, segment_index: int, lat: float, lng: float
) -> Tuple[List[Dict], List[Dict]]:
    """Split the route into completed and upcoming segments for rendering."""
    point_dicts = route["point_dicts"]
    current_point = {"lat": round(lat, 6), "lng": round(lng, 6)}

    tail_start = max(segment_index - 60, 0)
    trail = list(point_dicts[tail_start : segment_index + 1])
    if not trail or trail[-1] != current_point:
        trail.append(current_point)

    upcoming = [current_point] + point_dicts[segment_index + 1 :]
    if len(upcoming) <= 1:
        upcoming = []

    return trail, upcoming


def _determine_status(progress: float, speed: float, base_speed: float) -> str:
    if progress < 0.05:
        return "Departing Terminal"
    if progress > 0.95:
        return "Approaching Destination"
    if speed < base_speed * 0.6:
        return "Congested"
    return "En Route"


def get_tracking_snapshot() -> Dict:
    """
    Provide a ready-to-use snapshot for templates and APIs.
    """
    vehicles = generate_vehicle_data()
    statuses = sorted({vehicle["status"] for vehicle in vehicles})
    route_filters = sorted({vehicle["fleet_area"] for vehicle in vehicles})

    legend = {
        "routes": [
            {"name": route["name"], "color": route["color"]}
            for route in ROUTES
        ],
        "traffic": [
            {"label": "Heavy", "color": "#ef4444"},
            {"label": "Moderate", "color": "#f59e0b"},
            {"label": "Light", "color": "#22c55e"},
        ],
        "geofences": [
            {"name": fence["name"], "color": fence["color"]}
            for fence in GEOFENCES
        ],
    }

    return {
        "vehicles": vehicles,
        "status_filters": statuses,
        "fleet_filters": route_filters,
        "center_location": {
            "lat": BASE_LOCATION[0],
            "lng": BASE_LOCATION[1],
            "zoom": 11,
        },
        "generation_time": datetime.now(timezone.utc).isoformat(),
        "route_catalog": [
            {
                "id": route["id"],
                "name": route["name"],
                "color": route["color"],
                "distance_km": round(route["length_km"], 2),
                "loop_seconds": route["loop_seconds"],
                "origin": route["origin"],
                "destination": route["destination"],
            }
            for route in ROUTES
        ],
        "geofences": [dict(fence) for fence in GEOFENCES],
        "depots": [dict(depot) for depot in DEPOTS],
        "legend": legend,
    }
