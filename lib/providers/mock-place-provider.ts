import { mockPlaces } from '../domain/mock-data';
import type { PlaceProvider, NearbySearchInput } from './interfaces';
export class MockPlaceProvider implements PlaceProvider { async searchNearby(input:NearbySearchInput){const category=input.category;return mockPlaces.filter(place=>!category||category==='همه'||place.category===category)} }
export const mockPlaceProvider=new MockPlaceProvider();
