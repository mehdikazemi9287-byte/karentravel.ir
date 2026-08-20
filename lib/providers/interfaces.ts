import type { Booking, NearbyPlace, NotificationChannel, NotificationDispatch, TripEvent, TripNotification } from '../domain/travel';
export interface NearbySearchInput { latitude:number; longitude:number; radius:number; category?:string; sort?:'distance'|'relevance' }
export interface PlaceProvider { searchNearby(input:NearbySearchInput):Promise<NearbyPlace[]> }
export interface MapProvider { getViewport(input:{latitude:number;longitude:number;radius:number}):Promise<{center:[number,number];zoom:number}> }
export interface BookingProvider { createBooking(input:unknown):Promise<Booking> }
export interface NotificationProvider {
  listForTrip(tripId:string):Promise<TripNotification[]>;
  dispatchEvent(event:TripEvent,channels:NotificationChannel[]):Promise<NotificationDispatch[]>;
}
export interface PaymentProvider { authorize(input:unknown):Promise<{status:'authorized'|'declined';reference:string}> }
