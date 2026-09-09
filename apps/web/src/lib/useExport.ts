import { useCallback, useState } from "react";

type ExportFormat = "png" | "pdf";

export function useExport() {
  const [exporting, setExporting] = useState<ExportFormat | null>(null);

  const exportDashboard = useCallback(async (el: HTMLElement, format: ExportFormat, filename = "cortexbi-report") => {
    setExporting(format);
    try {
      const html2canvas = (await import("html2canvas-pro")).default;
      const canvas = await html2canvas(el, {
        scale: 2,
        useCORS: true,
        backgroundColor: "#FAFAF8",
        logging: false,
      });

      if (format === "png") {
        const link = document.createElement("a");
        link.download = `${filename}.png`;
        link.href = canvas.toDataURL("image/png");
        link.click();
      } else {
        const { jsPDF } = await import("jspdf");
        const imgData = canvas.toDataURL("image/png");
        const pxW = canvas.width;
        const pxH = canvas.height;
        const pdfW = 210; // A4 mm
        const pdfH = (pxH * pdfW) / pxW;
        const pdf = new jsPDF({ orientation: pdfH > pdfW ? "portrait" : "landscape", unit: "mm", format: [pdfW, pdfH] });
        pdf.addImage(imgData, "PNG", 0, 0, pdfW, pdfH);
        pdf.save(`${filename}.pdf`);
      }
    } finally {
      setExporting(null);
    }
  }, []);

  return { exporting, exportDashboard };
}
