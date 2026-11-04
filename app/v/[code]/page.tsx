import {VoucherCheck} from '../../../components/customer/VoucherCheck';
export const metadata = {title: 'بررسی اعتبار واچر', robots: {index: false}};
export default async function Page({params}: {params: Promise<{code: string}>}) {
  const {code} = await params;
  return <VoucherCheck code={code}/>;
}
