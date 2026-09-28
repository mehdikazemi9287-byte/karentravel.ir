'use client';
import {FormEvent,useState} from 'react';
import {useRouter} from 'next/navigation';
import {rentalRangeError} from '../../lib/rental-search';
export function CarRentalSearch(){
 const router=useRouter(),[error,setError]=useState('');
 function submit(e:FormEvent<HTMLFormElement>){e.preventDefault();const form=new FormData(e.currentTarget),city=String(form.get('destination')||'').trim(),start=String(form.get('depart')||''),end=String(form.get('return')||'');const problem=!city?'شهر تحویل خودرو را وارد کنید.':rentalRangeError(start,end);setError(problem);if(problem)return;router.push('/search/results?'+new URLSearchParams({vertical:'car_rental',destination:city,depart:start,return:end}));}
 return <form action="/search/results" className="panel" onSubmit={submit} noValidate><input type="hidden" name="vertical" value="car_rental"/><label style={{display:'block'}}>شهر تحویل<input name="destination" required/></label><label style={{display:'block'}}>تاریخ تحویل<input name="depart" type="date" required/></label><label style={{display:'block'}}>تاریخ بازگشت<input name="return" type="date" required/></label>{error&&<p role="alert">{error}</p>}<button className="button primary">جست‌وجوی خودرو</button></form>;
}
