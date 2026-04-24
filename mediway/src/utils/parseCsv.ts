export interface CsvRow {
  [key: string]: string;
}

export interface ParsedCsv {
  headers: string[];
  rows: CsvRow[];
  raw: string[][];
}

/** 한 줄을 파싱 (따옴표 이스케이프 지원) */
export function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inQuotes) {
      if (c === '"' && line[i + 1] === '"') {
        cur += '"';
        i++;
        continue;
      }
      if (c === '"') {
        inQuotes = false;
        continue;
      }
      cur += c;
    } else {
      if (c === '"') {
        inQuotes = true;
        continue;
      }
      if (c === ',') {
        out.push(cur);
        cur = '';
        continue;
      }
      cur += c;
    }
  }
  out.push(cur);
  return out.map((s) => s.trim());
}

/** 전체 CSV 텍스트 파싱. 빈 행 무시. BOM 제거. */
export function parseCsv(text: string): ParsedCsv {
  const cleaned = text.replace(/^\uFEFF/, '');
  const lines = cleaned.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) {
    return { headers: [], rows: [], raw: [] };
  }
  const headers = parseCsvLine(lines[0]);
  const raw = lines.slice(1).map(parseCsvLine);
  const rows = raw.map((cells) => {
    const row: CsvRow = {};
    headers.forEach((h, i) => {
      row[h] = cells[i] ?? '';
    });
    return row;
  });
  return { headers, rows, raw };
}

export function isValidEmail(s: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim());
}
