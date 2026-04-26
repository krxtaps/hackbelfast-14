import React from "react";
import ReactDOM from "react-dom/client";
import { registerLicense } from "@syncfusion/ej2-base";
import "leaflet/dist/leaflet.css";
import "@syncfusion/ej2-base/styles/material.css";
import "@syncfusion/ej2-buttons/styles/material.css";
import "@syncfusion/ej2-popups/styles/material.css";
import "@syncfusion/ej2-navigations/styles/material.css";
import "@syncfusion/ej2-notifications/styles/material.css";
import "@syncfusion/ej2-inputs/styles/material.css";
import "@syncfusion/ej2-lists/styles/material.css";
import "@syncfusion/ej2-dropdowns/styles/material.css";
import App from "./App";
import "./App.css";

registerLicense("Ngo9BigBOggjHTQxAR8/V1NDaF1cWGhIfEx1RHxQdld5ZFRHallYTnNWUj0eQnxTdENjXX1bcXRURmRaUkN2X0lfZA==");

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
