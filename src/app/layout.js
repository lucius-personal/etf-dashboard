import './globals.css';

export const metadata = {
  title: '台股 ETF 儀表板',
  description: '追蹤台股 ETF 的即時股價、折溢價、法人動向、配息紀錄',
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-TW">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
