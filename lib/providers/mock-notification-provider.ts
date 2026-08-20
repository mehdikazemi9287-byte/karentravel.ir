import { mockNotifications } from '../domain/mock-data';
import type { NotificationChannel, NotificationDispatch, TripEvent } from '../domain/travel';
import type { NotificationProvider } from './interfaces';

export class MockNotificationProvider implements NotificationProvider {
  async listForTrip(tripId:string){
    return mockNotifications.filter(notification=>notification.tripId===tripId);
  }

  async dispatchEvent(event:TripEvent,channels:NotificationChannel[]):Promise<NotificationDispatch[]> {
    return channels.map(channel=>({
      eventId:event.id,
      tripId:event.tripId,
      channel,
      deepLink:event.deepLink??`/trips/${event.tripId}?event=${event.id}`,
      status:'not-sent',
      reason:'mock-provider',
    }));
  }
}

export const mockNotificationProvider=new MockNotificationProvider();
