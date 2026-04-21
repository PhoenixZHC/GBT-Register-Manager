import type { GlobalThemeOverrides } from "naive-ui";

/** 与 DESIGN-apple.md 一致：中性色 + 唯一强调色 #0071e3 */
export const appleThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#0071e3",
    primaryColorHover: "#0077ed",
    primaryColorPressed: "#0066cc",
    primaryColorSuppl: "#0071e3",
    infoColor: "#0071e3",
    warningColor: "rgba(0, 0, 0, 0.48)",
    borderRadius: "8px",
    borderRadiusSmall: "5px",
    fontSize: "14px",
    fontSizeMedium: "14px",
    fontSizeLarge: "17px",
    bodyColor: "#1d1d1f",
    textColorBase: "#1d1d1f",
    textColor1: "#1d1d1f",
    textColor2: "rgba(0, 0, 0, 0.8)",
    textColor3: "rgba(0, 0, 0, 0.48)",
    cardColor: "#f5f5f7",
    modalColor: "#f5f5f7",
    popoverColor: "#f5f5f7",
    hoverColor: "rgba(0, 0, 0, 0.04)"
  },
  Button: {
    borderRadiusMedium: "8px",
    heightMedium: "44px",
    paddingMedium: "0 18px",
    fontSizeMedium: "14px",
    colorOpacitySecondary: "0.8",
    colorSecondary: "#1d1d1f",
    colorSecondaryHover: "#1d1d1f",
    colorSecondaryPressed: "#1d1d1f",
    border: "1px solid rgba(0, 0, 0, 0.12)",
    borderHover: "1px solid rgba(0, 0, 0, 0.18)",
    borderPressed: "1px solid rgba(0, 0, 0, 0.22)"
  },
  Card: {
    borderRadius: "8px",
    color: "#f5f5f7",
    titleFontSize: "17px",
    titleFontWeight: "600",
    paddingMedium: "20px 22px"
  },
  Input: {
    borderRadius: "8px",
    heightMedium: "44px"
  },
  Select: {
    peers: {
      InternalSelection: {
        borderRadius: "8px",
        heightMedium: "44px"
      }
    }
  },
  Form: {
    labelFontSizeTopMedium: "13px",
    blankHeightMedium: "12px"
  },
  DataTable: {
    borderRadius: "8px",
    thColor: "#fafafc",
    tdColor: "#f5f5f7",
    tdColorHover: "rgba(0, 113, 227, 0.06)"
  },
  Tag: {
    borderRadius: "8px"
  },
  Radio: {
    dotColorActive: "#0071e3",
    buttonBorderColor: "rgba(0, 0, 0, 0.12)",
    buttonBorderColorActive: "#0071e3",
    buttonBoxShadowFocus: "inset 0 0 0 1px #0071e3",
    buttonColorActive: "rgba(0, 113, 227, 0.12)"
  }
};
