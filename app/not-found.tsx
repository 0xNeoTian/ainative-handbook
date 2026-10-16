import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-24 text-center">
      <p className="text-sm font-medium text-fd-primary">404</p>
      <h1 className="text-2xl font-semibold">这一页不存在</h1>
      <p className="max-w-md text-fd-muted-foreground">可能是链接写错了，或者内容已经挪到别处。可以从目录重新找，或者用搜索。</p>
      <div className="flex gap-3">
        <Link href="/docs" className="rounded-lg bg-fd-primary px-4 py-2 text-sm font-medium text-fd-primary-foreground">
          打开手册目录
        </Link>
        <Link href="/" className="rounded-lg border px-4 py-2 text-sm font-medium">
          回到首页
        </Link>
      </div>
    </main>
  );
}
